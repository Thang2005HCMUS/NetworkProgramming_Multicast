import socket
import struct
import sys
import time

import cv2


MULTICAST_GROUP = "239.1.1.1"
PORT = 5004
FPS = 20
FRAME_INTERVAL = 1 / FPS
CHUNK_SIZE = 1000
JPEG_QUALITY = 80


def create_packet(seq, total, index, data):
    # Header format: 4-byte frame sequence, 2-byte total chunks, 2-byte chunk index.
    header = struct.pack("!IHH", seq, total, index)
    return header + data


def send_frame(sock, seq, frame):
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        return 0

    frame_bytes = encoded.tobytes()
    total_packets = (len(frame_bytes) + CHUNK_SIZE - 1) // CHUNK_SIZE

    for index in range(total_packets):
        start = index * CHUNK_SIZE
        chunk = frame_bytes[start:start + CHUNK_SIZE]
        packet = create_packet(seq, total_packets, index, chunk)
        sock.sendto(packet, (MULTICAST_GROUP, PORT))

    return total_packets


def main(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: cannot open video file: {video_path}")
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)

    seq = 0
    print(f"Streaming {video_path} to {MULTICAST_GROUP}:{PORT} at about {FPS} FPS")
    print("Nhấn Ctrl + C trên cửa sổ Terminal để dừng phát.")

    try:
        while True:
            frame_started_at = time.perf_counter()
            ret, frame = cap.read()

            if not ret:
                # Nếu seq == 0 tức là ngay từ đầu đã không đọc được -> File hỏng
                if seq == 0:
                    print("Lỗi: Không đọc được dữ liệu từ video. Vui lòng kiểm tra lại file!")
                    break
                
                print("\nVideo ended. Restarting from the first frame...")
                # CÁCH CHẮC CHẮN NHẤT: Đóng file cũ và load lại từ đầu
                cap.release()
                cap = cv2.VideoCapture(video_path)
                
                # Bỏ qua nhịp này để vòng lặp chạy lại và đọc frame mới
                continue

            packets_sent = send_frame(sock, seq, frame)
            
            # Ghi đè dòng in ra Terminal để màn hình log không bị trôi quá dài
            print(f"\rSent frame {seq} ({packets_sent} packets)", end="")
            seq += 1

            elapsed = time.perf_counter() - frame_started_at
            time.sleep(max(0, FRAME_INTERVAL - elapsed))
            
    except KeyboardInterrupt:
        # Bắt sự kiện người dùng bấm Ctrl + C để dừng vòng lặp
        print("\n\nServer stopped by user.")
    finally:
        if cap is not None:
            cap.release()
        sock.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python Server.py <file MJPEG>")
        sys.exit(1)

    main(sys.argv[1])
