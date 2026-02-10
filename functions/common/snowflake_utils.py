import time
import threading


class SnowflakeGenerator:
    """
    雪花算法实现 (Snowflake Algorithm)
    格式: 1位符号位 + 41位时间戳 + 10位机器ID + 12位序列号
    """
    def __init__(self, machine_id: int):
        self.twepoch = 1767268800000

        self.machine_id = machine_id
        self.machine_id_bits = 4
        self.max_machine_id = -1 ^ (-1 << self.machine_id_bits)

        if machine_id > self.max_machine_id or machine_id < 0:
            raise ValueError(f"Machine ID must be between 0 and {self.max_machine_id}")

        self.sequence = 0
        self.sequence_bits = 6
        self.machine_id_shift = self.sequence_bits
        self.timestamp_left_shift = self.sequence_bits + self.machine_id_bits
        self.sequence_mask = -1 ^ (-1 << self.sequence_bits)

        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _time_gen(self) -> int:
        return int(time.time() * 1000)

    def _til_next_millis(self, last_timestamp: int) -> int:
        timestamp = self._time_gen()
        while timestamp <= last_timestamp:
            timestamp = self._time_gen()
        return timestamp

    def generate(self) -> int:
        """生成一个新的 ID"""
        with self.lock:
            timestamp = self._time_gen()

            if timestamp < self.last_timestamp:
                raise Exception("Clock moved backwards. Refusing to generate id")

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.sequence_mask
                if self.sequence == 0:
                    timestamp = self._til_next_millis(self.last_timestamp)
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            new_id = ((timestamp - self.twepoch) << self.timestamp_left_shift) | \
                     (self.machine_id << self.machine_id_shift) | \
                     self.sequence
            return new_id


# 单例模式初始化，machine_id 可以从环境变量中读取（分布式环境下每个节点不同）
import os

worker_id = int(os.getenv("WORKER_ID", 1))
id_worker = SnowflakeGenerator(machine_id=worker_id)


def get_next_index_id() -> int:
    """全局调用接口"""
    return id_worker.generate()
