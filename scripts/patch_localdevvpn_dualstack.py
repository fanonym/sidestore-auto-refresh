from pathlib import Path
import sys
import re

root = Path(sys.argv[1]).resolve()

path = root / "Dependencies/minimuxer/Sources/Services/DeviceConnectionManager.swift"
text = path.read_text(encoding="utf-8")

old_filter = "                !$0.interfaceAddresses.v4.isEmpty && $0.interfaceAddresses.v6.isEmpty"
new_filter = "                !$0.interfaceAddresses.v4.isEmpty"

lines = text.splitlines(keepends=True)
changed = False

for index, line in enumerate(lines):
    content = line.rstrip("\r\n")
    newline = line[len(content):]

    if content.rstrip(" \t") == old_filter:
        lines[index] = new_filter + newline
        changed = True
        break

if changed:
    text = "".join(lines)
elif not any(line.rstrip("\r\n").rstrip(" \t") == new_filter for line in lines):
    raise SystemExit("Expected LocalDevVPN IPv4/IPv6 filter not found")

old_comment = "// Device connection strictly operates on IPv4 utun tunnels only"
new_comment = "// Device connection requires an IPv4 address; IPv6 presence does not disqualify the utun."

if old_comment in text:
    text = text.replace(old_comment, new_comment, 1)

marker = "[SIDESTORE_COREDEVICE] UTUN_CANDIDATE"

if marker not in text:
    old_probe = '''            for candidate in candidates {
                group.addTask { self.tcpProbe(candidate.ip) ? candidate : nil }
            }'''

    new_probe = '''            for candidate in candidates {
                group.addTask {
                    let reachable = self.tcpProbe(candidate.ip)
                    debugLog(
                        "[SIDESTORE_COREDEVICE] UTUN_CANDIDATE " +
                        "name=\\(candidate.tunnel.name) " +
                        "ip=\\(candidate.ip) " +
                        "ipv4_count=\\(candidate.tunnel.interfaceAddresses.v4.count) " +
                        "ipv6_count=\\(candidate.tunnel.interfaceAddresses.v6.count) " +
                        "reachable=\\(reachable)"
                    )
                    return reachable ? candidate : nil
                }
            }'''

    if old_probe not in text:
        raise SystemExit("Expected candidate probe block not found")

    text = text.replace(old_probe, new_probe, 1)

# Keep generated Swift free of trailing whitespace on the modified filter line.
text = re.sub(
    r'(?m)^(\\s*!\\$0\\.interfaceAddresses\\.v4\\.isEmpty)[ \\t]+$',
    r'\\1',
    text,
)

path.write_text(text, encoding="utf-8")

if marker not in text:
    raise SystemExit("Diagnostic marker was not installed")

print("patched LocalDevVPN dual-stack utun support and candidate diagnostics")
