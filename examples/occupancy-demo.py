#!/usr/bin/env python3
"""Occupancy module demo using the v3 occupancy.signal contract."""

from datetime import UTC, datetime, timedelta

from home_topology import Event, EventBus, EventFilter, LocationManager
from home_topology.modules.occupancy import OccupancyModule


def main() -> None:
    print("=" * 70)
    print("Occupancy Module Demo")
    print("=" * 70)

    # 1. Kernel setup
    loc_mgr = LocationManager()
    bus = EventBus()
    bus.set_location_manager(loc_mgr)

    loc_mgr.create_location(id="house", name="House")
    loc_mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
    loc_mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")

    for loc_id in ("house", "main_floor", "kitchen"):
        loc_mgr.set_module_config(
            location_id=loc_id,
            module_id="occupancy",
            config={
                "version": 1,
                "enabled": True,
                "default_timeout": 300,
                "default_trailing_timeout": 120,
                "occupancy_strategy": "independent",
                "contributes_to_parent": True,
            },
        )

    occupancy = OccupancyModule()
    occupancy.attach(bus, loc_mgr)

    # 2. Observe occupancy transitions
    events: list[Event] = []

    def on_occupancy_changed(event: Event) -> None:
        events.append(event)
        payload = event.payload
        status = "OCCUPIED" if payload["occupied"] else "VACANT"
        print(
            f"   {event.location_id}: {status} | reason={payload.get('reason')} "
            f"| contributions={len(payload.get('contributions', []))}"
        )

    bus.subscribe(on_occupancy_changed, EventFilter(event_type="occupancy.changed"))

    # 3. Publish normalized occupancy signals (what integrations do)
    print("\n1) TRIGGER kitchen from motion source")
    now = datetime.now(UTC)
    bus.publish(
        Event(
            type="occupancy.signal",
            source="demo",
            location_id="kitchen",
            entity_id="binary_sensor.kitchen_motion",
            payload={
                "event_type": "trigger",
                "source_id": "binary_sensor.kitchen_motion",
                "timeout": 300,
            },
            timestamp=now,
        )
    )

    print("\n2) CLEAR kitchen motion with trailing timeout")
    bus.publish(
        Event(
            type="occupancy.signal",
            source="demo",
            location_id="kitchen",
            entity_id="binary_sensor.kitchen_motion",
            payload={
                "event_type": "clear",
                "source_id": "binary_sensor.kitchen_motion",
                "timeout": 120,
            },
            timestamp=now + timedelta(seconds=5),
        )
    )

    print("\n3) Host executes timeout check")
    occupancy.check_timeouts(now + timedelta(seconds=130))

    print("\n4) Manual lock / unlock API")
    occupancy.trigger("kitchen", "manual", timeout=60, now=now + timedelta(seconds=140))
    occupancy.lock("kitchen", "vacation_mode", mode="freeze", scope="self")
    kitchen_state = occupancy.get_location_state("kitchen")
    if kitchen_state:
        print(
            f"   Kitchen locked={kitchen_state['is_locked']} "
            f"locked_by={kitchen_state['locked_by']}"
        )
    occupancy.unlock("kitchen", "vacation_mode")

    print("\n5) State persistence")
    state_dump = occupancy.dump_state()
    print(f"   Dumped locations: {len(state_dump)}")

    restored = OccupancyModule()
    restored.attach(bus, loc_mgr)
    restored.restore_state(state_dump)
    restored_state = restored.get_location_state("kitchen")
    if restored_state:
        print(
            f"   Restored kitchen occupied={restored_state['occupied']} "
            f"contributions={len(restored_state['contributions'])}"
        )

    print("\n" + "=" * 70)
    print(f"Events emitted: {len(events)}")
    print("Demo complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
