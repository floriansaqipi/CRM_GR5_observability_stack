"""MongoDB access has short deadlines; the controller can operate while it is down."""
import copy
import os
from pymongo import MongoClient, DESCENDING
from shared.model import ACTIVE, TERMINAL, utc_now
from shared.tracing import suppress_instrumentation


class Repository:
    def __init__(self):
        self.client = MongoClient(os.environ.get('MONGO_URI', 'mongodb://mongodb:27017/lab'),
                                 serverSelectionTimeoutMS=500, connectTimeoutMS=500,
                                 socketTimeoutMS=1000, timeoutMS=1000, retryWrites=False)
        self.db = self.client.get_default_database()
        self.available = False
        self.indexed = False

    def ping(self):
        with suppress_instrumentation():
            return self._ping()

    def _ping(self):
        try:
            self.client.admin.command('ping')
            if not self.indexed:
                self.db.runs.create_index([('created_at', DESCENDING)])
                self.db.workload_documents.create_index('expires_at', expireAfterSeconds=0)
                self.db.workload_documents.create_index('run_id')
                self.indexed = True
            self.available = True
        except Exception:
            self.available = False
        return self.available

    def save(self, record):
        document = copy.deepcopy(record)
        document['_id'] = document['id']
        self.db.runs.replace_one({'_id': document['id']}, document, upsert=True)
        if document['state'] in TERMINAL:
            self.db.workload_documents.delete_many({'run_id': document['id']})

    def get(self, run_id):
        record = self.db.runs.find_one({'_id': run_id}, {'_id': 0})
        return record

    def older_unfinished(self, cutoff):
        return list(self.db.runs.find({'state': {'$in': list(ACTIVE)}, 'created_at': {'$lt': cutoff}}, {'_id': 0}))

    def history(self, query, excluded, count):
        query = {**query, '_id': {'$nin': excluded}}
        total = self.db.runs.count_documents(query)
        return list(self.db.runs.find(query, {'_id': 0}).sort('created_at', DESCENDING).limit(count)), total

    def close(self):
        self.client.close()
