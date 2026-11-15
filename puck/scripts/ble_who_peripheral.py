#!/usr/bin/env python3
"""Advertise Calypso BLE `who` and notify when the puck updates the drop file.

Contract: docs/puck-phone-ble.md
Drop file: /tmp/calypso_who.json  (written by calypso_puck PhoneLink)

  pip install bless
  # Bluetooth on, then:
  python3 scripts/ble_who_peripheral.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ble_who")

SERVICE = "C41A0001-5E7A-4C1B-9A3D-CA1F5050C0DE"
WHO = "C41A0002-5E7A-4C1B-9A3D-CA1F5050C0DE"
CONTROL = "C41A0003-5E7A-4C1B-9A3D-CA1F5050C0DE"
EVENTS = "C41A0004-5E7A-4C1B-9A3D-CA1F5050C0DE"


async def main(drop: Path, name: str) -> None:
    try:
        from bless import (  # type: ignore
            BlessServer,
            GATTAttributePermissions,
            GATTCharacteristicProperties,
        )
    except ImportError as e:
        raise SystemExit(
            "bless not installed. On the Pi:  pip install bless\n" + str(e)
        )

    server = BlessServer(name=name, name_overwrite=True)

    # bless raises "Read/Write Callback is undefined" without these. Reads return
    # the current value (e.g. the latest `who`). Phone commands on `control`
    # (voice enrollment) are not implemented on the puck yet: log and ignore.
    def on_read(characteristic, **kwargs):
        return characteristic.value

    def on_write(characteristic, value, **kwargs):
        log.info("ignored phone command on %s: %s", characteristic.uuid,
                 bytes(value).decode("utf-8", "replace")[:120])

    server.read_request_func = on_read
    server.write_request_func = on_write
    gatt = {
        SERVICE: {
            WHO: {
                "Properties": (
                    GATTCharacteristicProperties.read
                    | GATTCharacteristicProperties.notify
                ),
                "Permissions": GATTAttributePermissions.readable,
                "Value": bytearray(b'{"status":"unknown"}'),
            },
            CONTROL: {
                "Properties": (
                    GATTCharacteristicProperties.write
                    | GATTCharacteristicProperties.write_without_response
                ),
                "Permissions": GATTAttributePermissions.writeable,
                "Value": bytearray(b""),
            },
            EVENTS: {
                "Properties": GATTCharacteristicProperties.notify,
                "Permissions": GATTAttributePermissions.readable,
                "Value": bytearray(b""),
            },
        }
    }
    await server.add_gatt(gatt)
    await server.start()
    log.info("advertising as %r — open Calypso on the phone", name)
    log.info("watching %s", drop)

    last_mtime: float | None = None
    last_payload = b""
    while True:
        try:
            st = drop.stat()
            if last_mtime is None or st.st_mtime_ns != last_mtime:
                last_mtime = st.st_mtime_ns
                payload = drop.read_bytes().strip()
                if payload and payload != last_payload:
                    last_payload = payload
                    if len(payload) > 180:
                        log.warning("payload %d bytes (>180) — phone may drop", len(payload))
                    char = server.get_characteristic(WHO)
                    char.value = bytearray(payload)
                    server.update_value(SERVICE, WHO)
                    log.info("notified who: %s", payload.decode("utf-8", "replace"))
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning("notify failed: %s", e)
        await asyncio.sleep(0.2)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--drop",
        default=os.environ.get("WHO_DROP_PATH", "/tmp/calypso_who.json"),
        type=Path,
    )
    p.add_argument("--name", default="Calypso Puck")
    args = p.parse_args()
    asyncio.run(main(args.drop, args.name))
