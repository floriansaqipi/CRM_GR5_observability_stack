"""An immutable assignment keeps work identical across limits and replicas."""
ALGORITHM = 'sum-squares-v1'
UNITS_PER_BATCH = 2500
UNIT_CHECKSUM = 150089160


def calculate_unit():
    return sum(n*n % 104729 for n in range(3000))


def assign_batches(batch_count, instances):
    slots_per_instance = 2 if len(instances) == 1 else 1
    plan = {service: [[] for _ in range(slots_per_instance)] for service in instances}
    for batch in range(batch_count):
        service = instances[batch % len(instances)]
        slot = (batch // len(instances)) % slots_per_instance
        plan[service][slot].append(batch)
    return plan
