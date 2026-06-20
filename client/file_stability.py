import os
import time

from client.config import FILE_STABLE_CHECKS, FILE_STABLE_INTERVAL_SEC


def wait_until_file_stable(file_path):
    previous_size = -1
    stable_count = 0

    for _ in range(60):
        if not os.path.exists(file_path):
            time.sleep(FILE_STABLE_INTERVAL_SEC)
            continue

        current_size = os.path.getsize(file_path)
        if current_size > 0 and current_size == previous_size:
            stable_count += 1
            if stable_count >= FILE_STABLE_CHECKS:
                return True
        else:
            stable_count = 0

        previous_size = current_size
        time.sleep(FILE_STABLE_INTERVAL_SEC)

    return False
