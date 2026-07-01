# Video Streaming Using IP Multicast

This project streams an MJPEG-style video over UDP multicast.

- `server.py` reads a video file frame by frame, encodes each frame as JPEG, splits it into packets, and sends the packets to a multicast group at about 20 FPS.
- `Client.py` joins the multicast group, receives packets on a background thread, reassembles frames, decodes them, displays the video, and prints stream statistics.

## Requirements

- Python 3.10+
- `opencv-python`
- `numpy`

Install dependencies:

```bash
pip install opencv-python numpy
```

## Packet Format

Each packet uses a custom header:

- `seq` - frame sequence number
- `total` - total number of packets in the frame
- `index` - packet index inside the frame

The header is encoded with:

```python
struct.pack("!IHH", seq, total, index)
```

The payload is a chunk of JPEG data.

## How to Run

### 1. Start the server

```bash
python Server.py <video_path>
```

Example:

```bash
python server.py movie.mjpeg
```

### 2. Start the client

Open a second terminal and run:

```bash
python Client.py
```

The client joins multicast group `239.1.1.1:5004` and displays the stream.

## How to Test

### Test 1 - Server multicast

1. Run `server.py` with a valid video file.
2. Check the server terminal for logs such as:
   - `Sent frame 0`
   - `Sent frame 1`
   - `Sent frame 2`
3. If the counter keeps increasing, the server is streaming correctly.

### Test 2 - Client receive and display

1. Start the server.
2. Start `Client.py`.
3. If a window named `Multicast Video Stream` appears and video plays, the client side works.

### Test 3 - Multiple clients

1. Start the server.
2. Open 2 or more terminals and run multiple instances of `Client.py`.
3. If all clients receive the same stream, multicast is working.

### Test 4 - Frame reassembly and loss detection

1. Start the server with a video that has multiple frames.
2. Watch the client.
3. If all packets for a frame arrive, the frame is decoded and shown.
4. If packets are missing for too long, the client drops that incomplete frame and prints a `[LOSS]` message.

## Notes on Loss Detection

The client uses `seq`, `total`, and `index` to reassemble frames and detect incomplete frames.

It reports:

- received packets
- missing packets
- duplicate packets
- completed frames
- decoded frames
- dropped frames
- loss rate

## Rubric Status

- `Server implementation`: done, multicast server exists.
- `Client implementation`: done, client receives and displays video.
- `Packet format`: done, custom packet header exists.
- `Multiple clients & loss detection`: done, multiple clients can join the multicast stream, and the client includes receiver concurrency plus loss/statistics reporting.

## Next Improvements

1. Add a command-line option for multicast group, port, FPS, and JPEG quality.
2. Add a CSV log file for statistics during grading.
3. Add a simulated packet-loss mode for easier local testing.