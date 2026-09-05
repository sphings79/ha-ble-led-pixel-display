# iPIXEL LED Matrix Bluetooth Protocol Documentation

**Complete Technical Documentation**  
*Based on Reverse Engineering Analysis*

Derived from:
- `github.com/yyewolf/go-ipxl`
- `github.com/sdolphin-JP/ipixel-ctrl`

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Bluetooth Services and Characteristics](#2-bluetooth-services-and-characteristics)
3. [Command Protocol Structure](#3-command-protocol-structure)
4. [Display Operations](#4-display-operations)
5. [Image and Animation Handling](#5-image-and-animation-handling)
6. [Appendix](#6-appendix)

---

## 1. Introduction

### 1.1 Overview

The iPIXEL LED Matrix system is a Bluetooth Low Energy (BLE) controlled display device that allows for dynamic content presentation through wireless communication. This documentation provides a comprehensive technical analysis of the Bluetooth protocol used to communicate with iPIXEL-compatible LED matrix displays, based on reverse engineering efforts from two open-source implementations:

- **go-ipxl** (Go implementation): A native Go library providing BLE control capabilities
- **ipixel-ctrl** (Python implementation): A Python-based control system with intercepted protocol analysis

### 1.2 Document Scope

This documentation covers:
1. Complete Bluetooth service and characteristic specifications
2. Detailed command protocol structure and encoding
3. Display control operations including power, brightness, and modes
4. Image and animation data transmission methods
5. Device initialization and connection sequences

### 1.3 Source Code References

All protocol specifications in this document are derived from and verified against actual source code. Each specification includes:
- File path references to the source implementation
- Line numbers for verification
- Actual byte sequences extracted from the code

#### Primary Source Files

**Go Implementation (go-ipxl):**
```
consts.go         # UUID definitions and constants
display.go        # Display control operations  
packet_builder.go # Packet construction logic
modes.go          # Mode switching commands
device_info.go    # Device information queries
utils.go          # Utility functions and CRC
```

**Python Implementation (ipixel-ctrl):**
```
bluetooth.py      # BLE connection management
commands/*.py     # Individual command implementations
image.py          # Image processing and conversion
utils.py          # CRC and utility functions
```

### 1.4 Protocol Architecture

The iPIXEL protocol operates over Bluetooth Low Energy using a client-server model:

- **Client**: Mobile app or control software (go-ipxl, ipixel-ctrl)
- **Server**: LED matrix display device
- **Transport**: BLE GATT (Generic Attribute Profile)
- **Communication**: Write commands with optional notify responses

#### Protocol Layers

```
┌─────────────────────────────────────┐
│ Application Layer (Display Control) │
├─────────────────────────────────────┤
│      Command Protocol Layer         │
├─────────────────────────────────────┤
│       Data Encoding Layer           │
├─────────────────────────────────────┤
│   GATT Layer (Characteristics)      │
├─────────────────────────────────────┤
│       BLE Transport Layer           │
└─────────────────────────────────────┘
```

### 1.5 Device Types

The protocol supports multiple LED matrix configurations, identified by device type bytes during initialization. Supported dimensions range from 32×16 pixels to 448×32 pixels, as documented in `go-ipxl/consts.go` lines 31-76.

### 1.6 Development History

The protocol has been reverse-engineered through:
1. Bluetooth packet interception from the official iPIXEL Color app
2. Analysis of communication patterns and command sequences
3. Implementation testing across multiple device types
4. Community collaboration and documentation efforts

---

## 2. Bluetooth Services and Characteristics

### 2.1 Service Discovery

iPIXEL LED matrix devices advertise themselves with specific naming patterns and service UUIDs. The device discovery process involves scanning for BLE peripherals with matching identifiers.

#### Device Naming Convention

Devices typically advertise with the prefix `LED_BLE_` followed by device-specific identifiers. This naming pattern is referenced in `ipixel-ctrl/docs/DeviceCommands.md` line 16.

### 2.2 GATT Characteristics

The protocol utilizes two primary GATT characteristics for bidirectional communication:

#### Write Characteristic (Command Transmission)

| Property | Value |
|----------|-------|
| UUID | `0000fa02-0000-1000-8000-00805f9b34fb` |
| Handle | `0x0006` |
| Properties | Write, Write Without Response |
| Source | `go-ipxl/consts.go` line 5<br>`ipixel-ctrl/bluetooth.py` line 19 |

This characteristic is used to send all commands from the client to the LED matrix device.

```go
// File: go-ipxl/consts.go, Line 5
UUIDWrite = "0000fa02-0000-1000-8000-00805f9b34fb"
```

```python
# File: ipixel-ctrl/bluetooth.py, Line 19
UUID_WRITE = "0000fa02-0000-1000-8000-00805f9b34fb"
```

#### Notify Characteristic (Response Reception)

| Property | Value |
|----------|-------|
| UUID | `0000fa03-0000-1000-8000-00805f9b34fb` |
| Handle | `0x0009` |
| Properties | Notify |
| Source | `go-ipxl/consts.go` line 6<br>`ipixel-ctrl/docs/DeviceCommands.md` line 17 |

```go
// File: go-ipxl/consts.go, Line 6
UUIDNotify = "0000fa03-0000-1000-8000-00805f9b34fb"
```

#### Notification Descriptor

To enable notifications, the client must write to the Client Characteristic Configuration Descriptor (CCCD):

| Property | Value |
|----------|-------|
| UUID | `00002902-0000-1000-8000-00805f9b34fb` |
| Handle | `0x000a` |
| Enable Value | `0x0100` (Little Endian) |
| Source | `ipixel-ctrl/docs/DeviceCommands.md` line 18 |

### 2.3 Connection Sequence

The complete connection and initialization sequence follows these steps:

1. **Device Discovery**
   - Scan for BLE peripherals
   - Filter by name prefix `LED_BLE_`
   - Extract device address

2. **Connection Establishment**
   - Connect to device by address
   - Set connection timeout (typically 10 seconds)
   - Verify connection stability

3. **Service Discovery**
   - Discover all GATT services
   - Locate write characteristic (`0000fa02-...`)
   - Locate notify characteristic (`0000fa03-...`)

4. **Notification Setup**
   - Find CCCD descriptor (`00002902-...`)
   - Write `0x0100` to enable notifications
   - Register notification callback handler

5. **Device Initialization**
   - Send device info request command
   - Parse response for screen dimensions
   - Send time synchronization command
   - Verify password if required

#### Connection Implementation (Go)

The Go implementation in `go-ipxl/display.go` lines 42-110 demonstrates the connection process:

```go
// File: go-ipxl/display.go, Lines 42-110
func (d *Display) Connect() error {
    // Enable BLE adapter
    err := d.adapter.Enable()
    // Scan for device
    ch, err := d.adapter.Scan(...)
    // Connect with timeout
    d.device, err = d.adapter.Connect(...)
    // Discover services
    svcs, err := d.device.DiscoverServices(nil)
    // Find characteristics
    chars, err := svc.DiscoverCharacteristics(nil)
    // Store write and notify characteristics
}
```

#### Connection Implementation (Python)

```python
# File: ipixel-ctrl/bluetooth.py
class BluetoothConnection:
    def connect(self, address):
        # Connect to device
        self.device = btle.Peripheral(address)
        # Enable notifications
        self.device.writeCharacteristic(0x000a, 
            struct.pack('<H', 0x0100))
        # Store write handle
        self.write_handle = 0x0006
```

### 2.4 MTU Considerations

The Maximum Transmission Unit (MTU) for BLE typically defaults to 23 bytes, with 3 bytes of overhead, leaving 20 bytes for payload data. Larger commands are automatically fragmented at the BLE layer.

### 2.5 Error Handling

Both implementations include error handling for common BLE issues:
- Connection timeouts (10 second default)
- Characteristic not found errors
- Write operation failures
- Notification registration failures
- Device disconnection events

---

## 3. Command Protocol Structure

### 3.1 Basic Command Format

All commands follow a consistent structure with a header containing length and command identifiers, followed by optional data payload. The basic format is documented in `ipixel-ctrl/commands/common.py` lines 6-8 and `ipixel-ctrl/docs/DeviceCommands.md` lines 5-9.

#### Standard Command Structure

```
[LEN_LOW][LEN_HIGH][CMD_LOW][CMD_HIGH][DATA...]
```

| Field | Size | Description |
|-------|------|-------------|
| LEN | 2 bytes | Total command size (Little Endian) |
| CMD | 2 bytes | Command opcode (Little Endian) |
| DATA | Variable | Command-specific payload |

#### Extended Data Command Structure

For commands transmitting images, GIFs, or other complex data, an extended header format is used as defined in `go-ipxl/packet_builder.go` lines 72-141:

```
[LENGTH(2)][TYPE(2)][OPT(1)][FRAME_LEN(4)][CRC(5)][DATA...]
```

### 3.2 Command Opcodes

#### Power and Control Commands

| Command | Opcode | Description | Source |
|---------|--------|-------------|---------|
| Power Control | `0x0107` | Turn display on/off | `set_power.py:28` |
| Brightness | `0x8004` | Set brightness (1-100) | `set_brightness.py:28` |
| Screen Select | `0x8007` | Select screen number | `set_screen.py:28` |
| Upside Down | `0x8006` | Flip display | `set_upside_down.py:28` |

#### Mode Commands

| Command | Opcode | Description | Source |
|---------|--------|-------------|---------|
| DIY Mode | `0x0104` | Enable DIY drawing | `set_diy_mode.py:29` |
| Default Mode | `0x8003` | Return to default | `set_default_mode.py:21` |
| Program Mode | `0x8008` | Set program sequence | `set_prg_mode.py:31` |
| Clock Mode | `0x0106` | Display clock | `set_clock_mode.py:76` |

#### Data Commands

| Command | Opcode | Description | Source |
|---------|--------|-------------|---------|
| PNG Data | `0x0002` | Send PNG image | `write_data_png.py:98` |
| GIF Data | `0x0003` | Send GIF animation | `write_data_gif.py:98` |
| Set Pixel | `0x0105` | Set individual pixel | `set_pixel.py:41` |
| Erase Data | `0x0102` | Clear stored data | `erase_data.py:43` |
| Set Time | `0x8001` | Sync clock time | `set_clock_mode.py:68` |

### 3.3 Command Examples

#### Power On Command

From `ipixel-ctrl/commands/set_power.py` line 28:

```python
# Command: 0x0107, Data: 0x01 (on)
command = [0x05, 0x00, 0x07, 0x01, 0x01]
# [LEN_L, LEN_H, CMD_L, CMD_H, DATA]
```

The Go implementation in `go-ipxl/display.go` line 141 confirms:

```go
// Power on: [5, 0, 7, 1, 1]
// Power off: [5, 0, 7, 1, 0]
cmd := []byte{5, 0, 7, 1, onByte}
```

#### Set Brightness Command

From `ipixel-ctrl/commands/set_brightness.py` line 28:

```python
# Command: 0x8004, Data: brightness value
brightness = 50
command = [0x05, 0x00, 0x04, 0x80, 0x32]
# [LEN_L, LEN_H, CMD_L, CMD_H, brightness]
```

#### Set Individual Pixel

From `ipixel-ctrl/commands/set_pixel.py` line 41:

```python
# Command: 0x0105
# Data: [R, G, B, A, X, Y]
color = 0xFF0000FF  # Red with full alpha
x, y = 10, 20
command = [0x0A, 0x00, 0x05, 0x01, 
           0xFF, 0x00, 0x00, 0xFF,  # RGBA
           0x0A, 0x14]              # X, Y
```

### 3.4 Data Type Encoding

The protocol uses specific type identifiers for different content types, as defined in `go-ipxl/consts.go` lines 9-28:

| Type | Value | Bytes | Description |
|------|-------|-------|-------------|
| TYPE_CAMERA | 0 | `[0, 0]` | Camera/Live feed |
| TYPE_VIDEO | 1 | `[1, 0]` | Video file |
| TYPE_IMAGE | 2 | `[2, 0]` | Static image |
| TYPE_GIF | 3 | `[3, 0]` | Animated GIF |
| TYPE_TEXT | 4 | `[0, 1]` | Text display |
| TYPE_DIY_IMAGE | 5 | `[5, 1]` | User drawing |
| TYPE_TEM | 7 | `[4, 0]` | Template |

### 3.5 CRC32 Calculation

For data integrity, CRC32 is used for image and animation data. The implementation is found in:
- Python: `ipixel-ctrl/utils.py` lines 31-41
- Go: `go-ipxl/utils.go` lines 40-43

```python
# File: ipixel-ctrl/utils.py, Lines 31-41
import zlib

def calculate_crc32(data):
    crc = zlib.crc32(data) & 0xFFFFFFFF
    # Return as 4-byte little-endian
    return struct.pack('<I', crc)
```

```go
// File: go-ipxl/utils.go, Lines 40-43
func calculateCRC32(data []byte) []byte {
    crc := crc32.ChecksumIEEE(data)
    return binary.LittleEndian.AppendUint32(nil, crc)
}
```

### 3.6 Response Handling

Devices respond through the notify characteristic with status codes and data. Response parsing varies by command type but generally follows:

1. Length validation
2. Command echo verification
3. Status code extraction
4. Payload parsing (if applicable)

---

## 4. Display Operations

### 4.1 Device Initialization

Before performing display operations, the device must be properly initialized. This process involves querying device capabilities and setting initial parameters.

#### Device Information Query

The device information command retrieves essential details about the LED matrix. From `go-ipxl/device_info.go` line 54:

```go
// Command structure: [8, 0, 1, 128, hour, minute, second, 0]
cmd := []byte{8, 0, 1, 128, 
    byte(time.Now().Hour()),
    byte(time.Now().Minute()), 
    byte(time.Now().Second()), 0}
```

The response contains:
- Device type byte (determines screen dimensions)
- MCU version
- WiFi module version
- Password protection flag

#### Screen Dimensions

Device types map to specific screen dimensions as defined in `go-ipxl/consts.go` lines 31-76:

| Type | Dimensions | Device Byte | Signed | Total Pixels |
|------|------------|-------------|---------|--------------|
| 0 | 64×64 | 128 | -128 | 4,096 |
| 1 | 96×16 | 132 | -124 | 1,536 |
| 2 | 32×32 | 129 | -127 | 1,024 |
| 3 | 64×16 | 131 | -125 | 1,024 |
| 4 | 32×16 | 130 | -126 | 512 |
| 5 | 64×20 | 133 | -123 | 1,280 |
| 6-8 | 128/144/192×16 | 134-136 | -122 to -120 | 2,048-3,072 |
| 9 | 48×24 | 137 | -119 | 1,152 |
| 10-19 | Various×32 | 138-147 | -118 to -109 | 2,048-14,336 |

### 4.2 Basic Display Controls

#### Power Management

Power control is fundamental to display operation. The implementation from `go-ipxl/display.go` lines 139-147:

```go
func (d *Display) SetPower(on bool) error {
    onByte := byte(0)
    if on {
        onByte = 1
    }
    // Command: [5, 0, 7, 1, onByte]
    return d.sendCommand([]byte{5, 0, 7, 1, onByte})
}
```

#### Brightness Control

Brightness ranges from 1 to 100. From `ipixel-ctrl/commands/set_brightness.py`:

```python
def set_brightness(device, brightness):
    # Validate range
    brightness = max(1, min(100, brightness))
    # Command: 0x8004
    command = struct.pack('<HHBB', 5, 0x8004, brightness)
    device.write(command)
```

#### Display Orientation

The display can be flipped using the upside-down command (`0x8006`):

```python
# Normal orientation
command = [0x05, 0x00, 0x06, 0x80, 0x00]

# Upside down
command = [0x05, 0x00, 0x06, 0x80, 0x01]
```

### 4.3 Display Modes

#### Clock Mode

Clock mode displays time with various styles. From `ipixel-ctrl/commands/set_clock_mode.py` lines 68-76:

```python
# Set current time (0x8001)
time_cmd = [0x08, 0x00, 0x01, 0x80,
            hour, minute, second, 0x00]

# Configure clock display (0x0106)
clock_cmd = [0x0B, 0x00, 0x06, 0x01,
    style,      # Display style (0-7)
    is_24h,     # 24-hour format flag
    show_date,  # Date display flag
    year, month, day, weekday]
```

Clock styles include:
- Style 0: Digital with seconds
- Style 1: Digital without seconds
- Style 2: Analog clock
- Style 3-7: Various decorative styles

#### DIY Drawing Mode

DIY mode enables pixel-by-pixel drawing. From `go-ipxl/modes.go`:

```go
func (d *Display) SetDIYMode(enabled bool) error {
    mode := byte(0)
    if enabled {
        mode = 1
    }
    // Command: [5, 0, 4, 1, mode]
    return d.sendCommand([]byte{5, 0, 4, 1, mode})
}
```

In DIY mode, individual pixels can be set using the `0x0105` command:

```python
# Set pixel at (x,y) to color RGBA
def set_pixel(x, y, r, g, b, a):
    command = [0x0A, 0x00, 0x05, 0x01,
               r, g, b, a,  # Color (RGBA)
               x, y]        # Position
    return command
```

#### Program Mode

Program mode cycles through stored content. From `ipixel-ctrl/commands/set_prg_mode.py`:

```python
# Select buffers 1, 3, and 5 for rotation
buffers = [1, 3, 5]
count = len(buffers)

# Command: 0x8008
command = [4 + count, 0x00, 0x08, 0x80,
           count & 0xFF, (count >> 8) & 0xFF]
command.extend(buffers)
```

### 4.4 Screen Management

#### Multiple Screen Support

Devices can store up to 9 screens (buffers). Screen selection from `ipixel-ctrl/commands/set_screen.py`:

```python
def select_screen(screen_number):
    # Validate screen number (1-9)
    screen = max(1, min(9, screen_number))
    # Command: 0x8007
    command = [0x05, 0x00, 0x07, 0x80, screen]
    return command
```

#### Data Management

Stored data can be erased selectively or completely. From `ipixel-ctrl/commands/erase_data.py`:

```python
# Erase specific buffers
buffers_to_erase = [2, 4, 6]
count = len(buffers_to_erase)

# Command: 0x0102
command = [4 + count, 0x00, 0x02, 0x01,
           count & 0xFF, (count >> 8) & 0xFF]
command.extend(buffers_to_erase)

# Erase all buffers
erase_all = [0x04, 0x00, 0x02, 0x01, 0x00, 0x00]
```

### 4.5 Real-time Updates

For smooth animations and real-time updates, the protocol supports rapid command transmission:

1. Enable DIY mode for direct pixel control
2. Send pixel update commands in batches
3. Use frame buffering for smooth transitions
4. Maintain consistent timing between updates

#### Performance Considerations

- BLE throughput typically 1-2 KB/s
- Full screen update (32×32): ~4KB uncompressed
- Compression via PNG/GIF reduces transfer time
- Batch multiple pixel updates in single command

---

## 5. Image and Animation Handling

### 5.1 Image Processing Pipeline

The protocol supports various image formats with automatic processing for LED matrix display. The implementation is detailed in `ipixel-ctrl/image.py` lines 35-63.

#### Image Format Conversion

All images undergo conversion to ensure compatibility:

```python
# File: ipixel-ctrl/image.py, Lines 35-63
def process_image(image, width, height, anchor):
    # Convert to RGBA format
    img = image.convert('RGBA')
    
    # Clip to device dimensions
    img = clip_image(img, width, height, anchor)
    
    # Export as PNG with compression
    output = BytesIO()
    img.save(output, format='PNG', 
             compress_level=6,
             icc_profile=None)
    
    return output.getvalue()
```

#### Anchor Positioning

Images can be anchored to different positions on the display:

| Anchor Flag | Value | Position |
|-------------|-------|----------|
| ALIGN_LEFT | `0x01` | Left edge alignment |
| ALIGN_RIGHT | `0x02` | Right edge alignment |
| ALIGN_TOP | `0x10` | Top edge alignment |
| ALIGN_BOTTOM | `0x20` | Bottom edge alignment |
| CENTER | `0x00` | Center (default) |

Combinations are possible:
- `0x11`: Top-left corner
- `0x12`: Top-right corner
- `0x21`: Bottom-left corner
- `0x22`: Bottom-right corner

### 5.2 PNG Image Transmission

PNG images are the primary format for static content. The protocol from `ipixel-ctrl/commands/write_data_png.py` line 98:

#### PNG Command Structure

```python
# Command: 0x0002
# Structure: [header][size][crc][buffer][data]

def send_png(png_data, buffer_number):
    size = len(png_data)
    crc = zlib.crc32(png_data) & 0xFFFFFFFF
    
    command = bytearray()
    # Header
    command.extend([total_len & 0xFF, total_len >> 8])
    command.extend([0x02, 0x00])  # Command 0x0002
    
    # Metadata
    command.append(0x00)  # Reserved
    command.extend(struct.pack('<I', size))
    command.extend(struct.pack('<I', crc))
    command.append(0x00)  # Reserved
    command.append(buffer_number)
    
    # PNG data
    command.extend(png_data)
    
    return command
```

#### Go Implementation

From `go-ipxl/packet_builder.go` lines 72-141:

```go
func buildImagePacket(data []byte, buffer int) []byte {
    // Type bytes for PNG
    typeBytes := []byte{2, 0}
    
    // Frame length (typically 1024)
    frameLen := make([]byte, 4)
    binary.LittleEndian.PutUint32(frameLen, 1024)
    
    // Calculate CRC32
    crc := crc32.ChecksumIEEE(data)
    crcBytes := make([]byte, 4)
    binary.LittleEndian.PutUint32(crcBytes, crc)
    
    // Build packet
    packet := append(typeBytes, 0)  // Type + option
    packet = append(packet, frameLen...)
    packet = append(packet, crcBytes...)
    packet = append(packet, 0, byte(buffer))
    packet = append(packet, data...)
    
    return packet
}
```

### 5.3 GIF Animation Support

Animated GIFs provide dynamic content capability. From `ipixel-ctrl/commands/write_data_gif.py`:

#### GIF Data Structure

```python
# Command: 0x0003 (similar to PNG but different opcode)
def send_gif(gif_data, buffer_number):
    size = len(gif_data)
    crc = zlib.crc32(gif_data) & 0xFFFFFFFF
    
    command = bytearray()
    # Header with command 0x0003
    command.extend([total_len & 0xFF, total_len >> 8])
    command.extend([0x03, 0x00])  # GIF command
    
    # Same metadata structure as PNG
    command.append(0x00)
    command.extend(struct.pack('<I', size))
    command.extend(struct.pack('<I', crc))
    command.append(0x00)
    command.append(buffer_number)
    
    # GIF data
    command.extend(gif_data)
    
    return command
```

#### Animation Playback

GIF animations are processed by the device firmware which:
1. Extracts individual frames
2. Respects frame timing from GIF metadata
3. Loops animation automatically
4. Scales frames to fit display dimensions

### 5.4 Text Rendering

Text can be displayed using the TEXT type. From `go-ipxl/consts.go` and `packet_builder.go`:

```go
// File: go-ipxl/consts.go
TYPE_TEXT = 4

// File: go-ipxl/packet_builder.go
// Text type bytes: [0, 1]
case TYPE_TEXT:
    typeBytes = []byte{0, 1}
```

Text packets include:
- Text string (UTF-8 encoded)
- Font size parameter
- Color information
- Scrolling speed (for long text)

### 5.5 Video Streaming

The protocol supports video streaming through the VIDEO type:

```go
// File: go-ipxl/consts.go
TYPE_VIDEO = 1

// Video type bytes: [1, 0]
case TYPE_VIDEO:
    typeBytes = []byte{1, 0}
```

Video frames are sent as individual images with timing information for synchronized playback.

### 5.6 Performance Optimization

#### Compression Strategies

1. **PNG Compression**: Level 6 provides good balance
2. **Color Reduction**: Reduce to 256 colors when possible
3. **Resolution Matching**: Pre-scale to exact display size
4. **Frame Skipping**: For video, reduce FPS to match BLE bandwidth

#### Buffer Management

The device supports 9 content buffers (screens 1-9):

```python
# Pre-load multiple images
for i, image in enumerate(images[:9]):
    buffer_number = i + 1
    send_png(image, buffer_number)

# Quick switching between pre-loaded content
select_screen(1)  # Instant switch
delay(1000)
select_screen(2)  # No transmission needed
```

### 5.7 Image Size Calculations

#### Data Requirements

| Display | Pixels | Raw RGB | Typical PNG |
|---------|--------|---------|-------------|
| 32×16 | 512 | 1.5 KB | 0.3-0.5 KB |
| 32×32 | 1,024 | 3 KB | 0.5-1 KB |
| 64×32 | 2,048 | 6 KB | 1-2 KB |
| 64×64 | 4,096 | 12 KB | 2-4 KB |
| 128×32 | 4,096 | 12 KB | 2-4 KB |
| 256×32 | 8,192 | 24 KB | 4-8 KB |

#### Transfer Time Estimates

At typical BLE throughput of 1-2 KB/s:
- 32×32 PNG: 0.5-1 second
- 64×64 PNG: 2-4 seconds
- Full GIF animation: 5-30 seconds depending on frames

### 5.8 Error Handling

Both implementations include error handling for:
- Invalid image formats
- Oversized data (exceeds BLE MTU limits)
- CRC validation failures
- Buffer overflow (more than 9 screens)
- Unsupported color modes

---

## 6. Appendix

### 6.1 Complete Command Reference

#### Command Opcode Summary

| Opcode | Name | Description | Data Length |
|--------|------|-------------|-------------|
| `0x0102` | ERASE_DATA | Clear stored buffers | Variable |
| `0x0104` | DIY_MODE | Enable/disable DIY mode | 1 byte |
| `0x0105` | SET_PIXEL | Set individual pixel color | 6 bytes |
| `0x0106` | CLOCK_MODE | Configure clock display | 7 bytes |
| `0x0107` | POWER | Power on/off | 1 byte |
| `0x0002` | PNG_DATA | Send PNG image | Variable |
| `0x0003` | GIF_DATA | Send GIF animation | Variable |
| `0x8001` | SET_TIME | Set current time | 4 bytes |
| `0x8003` | DEFAULT_MODE | Return to default mode | 0 bytes |
| `0x8004` | BRIGHTNESS | Set brightness (1-100) | 1 byte |
| `0x8006` | UPSIDE_DOWN | Flip display | 1 byte |
| `0x8007` | SELECT_SCREEN | Choose buffer (1-9) | 1 byte |
| `0x8008` | PROGRAM_MODE | Set program sequence | Variable |
| `0x8101` | DEVICE_INFO | Request device information | 4 bytes |

### 6.2 Implementation Examples

#### Python: Complete Connection Example

```python
import struct
import time
from bluepy import btle

class IPIXELDisplay:
    UUID_WRITE = "0000fa02-0000-1000-8000-00805f9b34fb"
    UUID_NOTIFY = "0000fa03-0000-1000-8000-00805f9b34fb"
    
    def __init__(self, address):
        self.address = address
        self.device = None
        
    def connect(self):
        # Connect to device
        self.device = btle.Peripheral(self.address)
        
        # Enable notifications
        self.device.writeCharacteristic(0x000a, 
            struct.pack('<H', 0x0100))
        
        # Get device info
        self.get_device_info()
        
        # Sync time
        self.set_time()
        
    def send_command(self, command):
        # Write to characteristic handle 0x0006
        self.device.writeCharacteristic(0x0006, 
            bytearray(command))
    
    def power_on(self):
        self.send_command([0x05, 0x00, 0x07, 0x01, 0x01])
    
    def set_brightness(self, level):
        self.send_command([0x05, 0x00, 0x04, 0x80, level])
    
    def set_pixel(self, x, y, r, g, b):
        cmd = [0x0A, 0x00, 0x05, 0x01, 
               r, g, b, 0xFF, x, y]
        self.send_command(cmd)
    
    def set_time(self):
        now = time.localtime()
        cmd = [0x08, 0x00, 0x01, 0x80,
               now.tm_hour, now.tm_min, 
               now.tm_sec, 0x00]
        self.send_command(cmd)
        
    def get_device_info(self):
        now = time.localtime()
        cmd = [0x08, 0x00, 0x01, 0x80,
               now.tm_hour, now.tm_min,
               now.tm_sec, 0x00]
        self.send_command(cmd)
        # Parse response from notification
```

#### Go: Complete Connection Example

```go
package main

import (
    "encoding/binary"
    "time"
    "tinygo.org/x/bluetooth"
)

type Display struct {
    device       bluetooth.Device
    writeChar    bluetooth.DeviceCharacteristic
    notifyChar   bluetooth.DeviceCharacteristic
    adapter      *bluetooth.Adapter
}

const (
    UUIDWrite  = "0000fa02-0000-1000-8000-00805f9b34fb"
    UUIDNotify = "0000fa03-0000-1000-8000-00805f9b34fb"
)

func NewDisplay(address string) *Display {
    return &Display{
        adapter: bluetooth.DefaultAdapter,
    }
}

func (d *Display) Connect(address string) error {
    // Enable adapter
    err := d.adapter.Enable()
    if err != nil {
        return err
    }
    
    // Connect to device
    d.device, err = d.adapter.Connect(
        bluetooth.Address{address},
        bluetooth.ConnectionParams{})
    if err != nil {
        return err
    }
    
    // Discover services
    svcs, err := d.device.DiscoverServices(nil)
    if err != nil {
        return err
    }
    
    // Find characteristics
    for _, svc := range svcs {
        chars, _ := svc.DiscoverCharacteristics(nil)
        for _, char := range chars {
            if char.UUID().String() == UUIDWrite {
                d.writeChar = char
            }
            if char.UUID().String() == UUIDNotify {
                d.notifyChar = char
                char.EnableNotifications(d.handleNotify)
            }
        }
    }
    
    // Initialize device
    d.getDeviceInfo()
    d.setTime()
    
    return nil
}

func (d *Display) sendCommand(cmd []byte) error {
    _, err := d.writeChar.WriteWithoutResponse(cmd)
    return err
}

func (d *Display) PowerOn() error {
    return d.sendCommand([]byte{5, 0, 7, 1, 1})
}

func (d *Display) SetBrightness(level byte) error {
    return d.sendCommand([]byte{5, 0, 4, 128, level})
}

func (d *Display) SetPixel(x, y, r, g, b byte) error {
    cmd := []byte{10, 0, 5, 1, r, g, b, 255, x, y}
    return d.sendCommand(cmd)
}

func (d *Display) handleNotify(data []byte) {
    // Process notification data
}
```

### 6.3 Troubleshooting Guide

#### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| Device not found during scan | Ensure device is powered on and in range. Check battery level. |
| Connection timeout | Move closer to device. Disable other Bluetooth connections. |
| Write characteristic not found | Verify correct UUID. Ensure service discovery completed. |
| Commands not working | Enable notifications first. Check command byte order. |
| Display not updating | Verify power state. Check brightness level (not zero). |
| Image corrupted | Validate CRC32. Check PNG compression settings. |
| Animation not playing | Confirm GIF format. Check file size limits. |

#### Debugging Commands

```python
# Test connection
power_on = [0x05, 0x00, 0x07, 0x01, 0x01]

# Test display (set to maximum brightness)
max_brightness = [0x05, 0x00, 0x04, 0x80, 0x64]

# Test pixel (red pixel at 0,0)
test_pixel = [0x0A, 0x00, 0x05, 0x01, 
              0xFF, 0x00, 0x00, 0xFF, 0x00, 0x00]

# Clear all buffers
clear_all = [0x04, 0x00, 0x02, 0x01, 0x00, 0x00]

# Reset to default
default_mode = [0x04, 0x00, 0x03, 0x80]
```

### 6.4 Protocol Limitations

#### Known Constraints

1. **Buffer Count**: Maximum 9 screens/buffers
2. **Brightness Range**: 1-100 (0 is invalid)
3. **BLE MTU**: Default 20 bytes payload
4. **Transfer Speed**: Limited to 1-2 KB/s typical
5. **Color Depth**: 24-bit RGB (8 bits per channel)
6. **Text Encoding**: UTF-8 only
7. **Animation Format**: GIF87a/GIF89a only
8. **Image Format**: PNG with RGBA support

#### Protocol Versions

Different device firmware versions may support different command sets:
- Version 1.x: Basic commands only
- Version 2.x: Added GIF support
- Version 3.x: Enhanced text rendering
- Version 4.x: Multiple screen support

### 6.5 Security Considerations

#### Authentication

Some devices require password authentication:

```python
# Check if password required (from device info response)
if device_info.password_required:
    # Send password (default: "0000")
    password_cmd = [0x08, 0x00, 0xFF, 0x80,
                    '0', '0', '0', '0']
    send_command(password_cmd)
```

#### Encryption

The protocol does not implement encryption beyond standard BLE security:
- Use BLE pairing when available
- Implement application-level encryption for sensitive content
- Avoid transmitting personal information

### 6.6 References and Resources

#### Source Repositories
- **go-ipxl**: https://github.com/yyewolf/go-ipxl
- **ipixel-ctrl**: https://github.com/sdolphin-JP/ipixel-ctrl

#### Related Projects
- **python3-idotmatrix-client**: Alternative Python implementation
- **BluetoothRocks/Matrix**: WebBluetooth implementation
- **Pixelix**: ESP32-based LED matrix firmware

#### Specifications
- Bluetooth Core Specification v4.0+
- GATT Profile Specification
- PNG Specification (ISO/IEC 15948)
- GIF89a Specification

---

## License and Credits

This documentation is derived from open-source implementations and reverse engineering efforts. All protocol information is based on publicly available source code from:

- go-ipxl by yyewolf (Go implementation)
- ipixel-ctrl by sdolphin-JP (Python implementation)

The protocol itself is proprietary to the iPIXEL device manufacturers. This documentation is provided for educational and interoperability purposes.
---

## Appendix A: Commands recovered from the vendor app

Everything above was reconstructed from observed Bluetooth traffic, by
`ipixel-ctrl`, `go-ipxl` and `pypixelcolor`. This appendix comes from a
different source: static analysis of the vendor Android app **iPixel Color
3.7.7** (`com.wifiled.ipixels`, versionCode 379), decompiled with jadx.

Reading the app rather than the wire shows commands the app *can* send but
rarely does, which traffic capture cannot reveal. Seven of the entries below
appear in none of the three projects.

Source: `com/wifiled/ipixels/core/send/BaseSend.kt`.

### A.1 Frame format

Confirmed by every command in the app:

```
[LEN_L, LEN_H, CMD_L, CMD_H, DATA...]
```

`LEN` is the total frame length, little-endian. The opcode is
`CMD_H << 8 | CMD_L`, so the bytes appear byte-swapped in the frame.

### A.2 Command table

| Opcode | Frame | App method | Notes |
|---|---|---|---|
| `0x0107` | `05 00 07 01 <onOff>` | `sendLedOnOff` | Power. Already known. |
| `0x8004` | `05 00 04 80 <level>` | `setLedLight` | Brightness 1–100. Already known. |
| `0x8006` | `05 00 06 80 <isDown>` | `setUpsideDown` | Flip display. Already known. |
| `0x8003` | `04 00 03 80` | `deleteAllData` | Clear stored data. Already known. |
| `0x0104` | `05 00 04 01 <mode>` | `setDiyFunMode` | DIY mode. Already known. |
| `0x0106` | `0B 00 06 01 01 01 00 00 00 00 00` | `sendColockMode` | Clock. Already known. |
| **`0x0006`** | `07 00 06 00 00 00 00` | `sendSportData` | **New.** Step count, speed, decimals. |
| **`0x0200`** | `06 00 00 02 00 00` | `sendRhythm` | **New.** Music visualiser, level and mode. |
| **`0x0201`** | `10 00 01 02 <mode> …` | `sendRhythmChart` | **New.** Spectrum payload, 16-byte frame. |
| **`0x0204`** | `08 00 04 02 <flag> <p1> <p2> <p3>` | `setPwd` | **New.** Sets a device password. |
| **`0x0205`** | `07 00 05 02 <p1> <p2> <p3>` | `verifyPwd` | **New.** Verifies the password. |
| **`0x8012`** | `05 00 12 80 <weekday>` | `setWeek` | **New.** Sets the weekday. |
| **`0x55AA`** | `05 00 AA 55 02` | `upDataOTA2900Start` | **New.** Starts a firmware update. |
| **`0xC0..`** | `0D 00 <otaType> C0 <pkgCount> <CRC32>` | `updateOtaMcuOrWifiStep1` | **New.** Firmware upload; `CMD_L` carries the OTA target. |

Password bytes are sent as three separate decimal digits parsed from a
string, not as ASCII — `Byte.parseByte()` on two-character substrings.

### A.3 There is no way to read device state

This matters for any integration that wants to show whether a panel is on.

The only inbound path is `BleManager.onChanged()`, and it treats responses as
flow control for bulk transfers, nothing else:

```java
if (value.length < 4 || value[0] != 5) { ... }
else {
    byte b = value[4];
    if (b == 1)      { sendBleDataThread.clear12kDataQueue(); }
    else if (b == 3) { ...clearTotalDataQueue(); }
}
```

`value[4]` is a buffer signal, not a status field. There is no query for power
state, brightness, current mode or anything else. **The vendor app does not
know whether the panel is on either** — it only remembers what it last sent.

Four independent sources now agree: the three open-source projects, all built
from traffic capture, and the app itself. Any integration can only track the
state it wrote, never read it back.

### A.4 Content API

The app loads its picture and animation archive from a server. Endpoints found
in the DEX:

| Endpoint | Purpose |
|---|---|
| `https://manage.heaton.com.cn/api/rm/getMaterialUnderCategory?sign=` | Assets by category |
| `http://app.heaton.cn/sucai_define.json` | Category definitions per panel geometry |
| `http://app.heaton.cn/homeConfig.json` | Home screen configuration |
| `https://api.e-toys.cn/api/app/bluetoothFilter` | Which BLE devices the app accepts |
| `https://api.e-toys.cn/api/app/lastUpdate` | Version check |

`assets/sucai_define.json` inside the APK lists 49 panel geometries, each with
its own categories. The category keys are Chinese (`热点` hotspot, `表情` emoji,
`驾驶` drive, `时节` season, `创意` originality) and are passed to the server as
`requestKey`.

This is documented for completeness. The archive contents belong to the
vendor, so this project neither bundles them nor provides a downloader.

### A.5 Device types, panel geometry and product ids

The device-info response carries a device type byte. It does not map to a
resolution directly: it maps to an internal LED type, and for three device
types the mapping additionally depends on the product id, because the same
resolution ships in more than one hardware generation with different buffer
sizes.

`pypixelcolor` covers device types 128-147 and LED types 0-19, inherited from
`go-ipxl`. The app carries device types up to 159 and 36 LED types.

Source: `ChooseActivity.setLedType()` and `AppConfig.ledSizeMap`.

| Device type | LED type | Size | Frame size | Text size | WiFi |
|---|---|---|---|---|---|
| 0 | 0 | 64×64 | 12288 | | yes |
| 128 | 0 | 64×64 | 12288 | | |
| 129 | 2, or **21** when pid=55 | 32×32 | 12288 | | |
| 130 | 4, or **22** when pid=56 | 32×16 | | | |
| 131 | 3 | 64×16 | | | |
| 132 | 1 | 96×16 | | | |
| 133 | 5 | 64×20 | | | |
| 134 | 6 | 128×32 | | 32 | no |
| 135 | 7 | 144×16 | | | |
| 136 | 8 | 192×16 | | | |
| 137 | 9, or **23** when pid=57 | 48×24 | | 24 | |
| 138–147 | 10–19 | see LED size map | | 32 | |
| **148** | **20** | **16×16** | | 16 | |
| **149–158** | **24–33** | **96×64 … 512×64** | | 64 | |
| **159** | **34/35** | **576×64 / 640×64** | | 64 | |

LED size map, indexed by LED type:

```
 0: 64×64    6: 128×32   12: 128×32   18: 384×32   24: 64×64    30: 320×64
 1: 96×16    7: 144×16   13: 96×32    19: 448×32   25: 96×64    31: 384×64
 2: 32×32    8: 192×16   14: 160×32   20: 16×16    26: 128×64   32: 448×64
 3: 64×16    9: 48×24    15: 192×32   21: 32×32    27: 160×64   33: 512×64
 4: 32×16   10: 64×32    16: 256×32   22: 32×16    28: 192×64   34: 576×64
 5: 64×20   11: 96×32    17: 320×32   23: 48×24    29: 256×64   35: 640×64
```

Six resolutions appear twice. The device type, not the resolution, identifies
the hardware.

Frame size defaults to 4096 in the app and rises to 12288 for LED types 0, 2
and 21. `go-ipxl` assumes 1024 throughout.

### A.6 Product ids and brands

Panels report a `cid` (4 digits) and `pid` (2 digits); together these form the
`cidpid` the app uses to identify a model. `http://app.heaton.cn/homeConfig.json`
groups them by brand:

| cidpid | Brand |
|---|---|
| `002501`–`002509`, `002513`, `002514` | **HYPERLITE** |
| `002510`, `002511`, `002512` | **EZYEVY** |

`assets/sucai_define.json` references further ids outside that range:
`000112`, `000120`, `000145`, `000154`–`000157`, `000701`, `000702`, `000704`,
`003301`, `003401`. So there are at least four cid groups — `0001`, `0007`,
`0025` and `0033`/`0034` — behind what is otherwise the same hardware family,
also sold as BGLight and as the B.K. Light LED Pixel Board.

The `bluetoothFilter` endpoint returns a single entry, `---00`, last changed in
September 2023. It is an exclusion pattern, not a list of supported prefixes.

### A.7 Firmware updates

`upDataOTA2900Start` (`0x55AA`) and `updateOtaMcuOrWifiStep1` (`0xC0xx`, with
the OTA target in `CMD_L`) upload firmware over Bluetooth, and
`https://api.e-toys.cn/api/app/firmwareInfo` reports what is available.

**This integration deliberately implements only the version check, not the
upload.** The command set is only partially understood — "step 1" implies at
least one further step that has not been recovered — and these panels have no
recovery mode anyone has documented. A failed write would likely be
unrecoverable, and firmware is something one updates once every few years,
which the vendor app already does reliably.
