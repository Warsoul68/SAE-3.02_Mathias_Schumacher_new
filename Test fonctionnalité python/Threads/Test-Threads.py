import threading
import time

def task(i):
    print(f"Je suis la thread {i}")
    time.sleep(2)

if __name__ == '__main__':
    start = time.perf_counter()

    task(1)
    task(2)

    for i in range(4):
        print(task(1))
        print(task(2))

    end = time.perf_counter()
    print(f"Tasks ended in {round(end - start, 2)} second(s)")