import queue
import socket
import struct
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np


MULTICAST_GROUP = "239.1.1.1"
PORT = 5004
HEADER_SIZE = 8
FRAME_TIMEOUT = 0.25
STATS_INTERVAL = 2.0


@dataclass
class FrameBuffer:
    total: int
    created_at: float
    chunks: dict


@dataclass
class StreamStats:
    received_packets: int = 0
    duplicate_packets: int = 0
    completed_frames: int = 0
    decoded_frames: int = 0
    dropped_frames: int = 0
    missing_packets: int = 0

    def loss_rate(self):
        expected = self.received_packets + self.missing_packets
        if expected == 0:
            return 0.0
        return (self.missing_packets / expected) * 100


def join_multicast_group():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", PORT))

    membership = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
    sock.settimeout(0.1)

    return sock, membership


def cleanup_expired_frames(frames, stats, now):
    expired = [
        seq for seq, frame in frames.items()
        if now - frame.created_at > FRAME_TIMEOUT
    ]

    for seq in expired:
        frame = frames.pop(seq)
        missing = frame.total - len(frame.chunks)
        if missing > 0:
            stats.dropped_frames += 1
            stats.missing_packets += missing
            print(f"[LOSS] Dropped frame {seq}: missing {missing}/{frame.total} packets")


def receiver_loop(sock, frame_queue, stop_event, stats):
    frames = {}
    last_cleanup = time.monotonic()

    while not stop_event.is_set():
        try:
            packet, _ = sock.recvfrom(65535)
        except socket.timeout:
            now = time.monotonic()
            cleanup_expired_frames(frames, stats, now)
            continue
        except OSError:
            break

        if len(packet) < HEADER_SIZE:
            continue

        header = packet[:HEADER_SIZE]
        data = packet[HEADER_SIZE:]
        seq, total, index = struct.unpack("!IHH", header)

        if total == 0 or index >= total:
            continue

        now = time.monotonic()
        frame = frames.get(seq)
        if frame is None:
            frame = FrameBuffer(total=total, created_at=now, chunks={})
            frames[seq] = frame

        if index in frame.chunks:
            stats.duplicate_packets += 1
            continue

        frame.chunks[index] = data
        stats.received_packets += 1

        if len(frame.chunks) == frame.total:
            frame_data = b"".join(frame.chunks[i] for i in range(frame.total))
            try:
                frame_queue.put_nowait((seq, frame_data))
            except queue.Full:
                stats.dropped_frames += 1
                print(f"[DROP] Display queue full. Dropped completed frame {seq}")
            stats.completed_frames += 1
            del frames[seq]

        if now - last_cleanup >= FRAME_TIMEOUT:
            cleanup_expired_frames(frames, stats, now)
            last_cleanup = now


def print_stats(stats):
    print(
        "[STATISTICS] "
        f"received_packets={stats.received_packets} "
        f"missing_packets={stats.missing_packets} "
        f"duplicate_packets={stats.duplicate_packets} "
        f"completed_frames={stats.completed_frames} "
        f"decoded_frames={stats.decoded_frames} "
        f"dropped_frames={stats.dropped_frames} "
        f"loss_rate={stats.loss_rate():.2f}%"
    )


def main():
    sock, membership = join_multicast_group()
    frame_queue = queue.Queue(maxsize=60)
    stop_event = threading.Event()
    stats = StreamStats()

    receiver = threading.Thread(
        target=receiver_loop,
        args=(sock, frame_queue, stop_event, stats),
        daemon=True,
    )
    receiver.start()

    print(f"Joined multicast group {MULTICAST_GROUP}:{PORT}")
    print("Press 'q' in the video window to exit.")

    last_stats_at = time.monotonic()

    try:
        while True:
            try:
                seq, frame_data = frame_queue.get(timeout=0.03)
            except queue.Empty:
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                stats.decoded_frames += 1
                cv2.imshow("Multicast Video Stream", frame)

            now = time.monotonic()
            if now - last_stats_at >= STATS_INTERVAL:
                print_stats(stats)
                last_stats_at = now

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        print("\nClient stopped by user.")
    finally:
        stop_event.set()
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, membership)
        sock.close()
        receiver.join(timeout=1.0)
        cv2.destroyAllWindows()
        print("Left multicast group.")
        print_stats(stats)


if __name__ == "__main__":
    main()
