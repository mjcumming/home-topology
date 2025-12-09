"""Tests for PresenceModule."""

import pytest

from home_topology import LocationManager, EventBus, Event
from home_topology.modules.presence import PresenceModule


class TestPresenceModuleBasics:
    """Test basic PresenceModule functionality."""

    def test_module_properties(self):
        """Test module ID and version."""
        module = PresenceModule()

        assert module.id == "presence"
        assert module.CURRENT_CONFIG_VERSION == 1

    def test_attach_to_kernel(self):
        """Test attaching to kernel components."""
        loc_mgr = LocationManager()
        bus = EventBus()
        module = PresenceModule()

        module.attach(bus, loc_mgr)

        assert module._bus is bus
        assert module._loc_manager is loc_mgr

    def test_default_config(self):
        """Test default configuration."""
        module = PresenceModule()
        config = module.default_config()

        assert config["version"] == 1
        assert config["enabled"] is True


class TestPersonManagement:
    """Test person creation and management."""

    @pytest.fixture
    def module(self):
        """Create PresenceModule instance."""
        return PresenceModule()

    def test_create_person(self, module):
        """Test creating a person."""
        person = module.create_person(
            id="mike", name="Mike", device_trackers=["device_tracker.phone"]
        )

        assert person.id == "mike"
        assert person.name == "Mike"
        assert person.device_trackers == ["device_tracker.phone"]
        assert person.current_location_id is None
        assert person.primary_tracker == "device_tracker.phone"

    def test_create_person_duplicate_error(self, module):
        """Test creating duplicate person raises error."""
        module.create_person(id="mike", name="Mike")

        with pytest.raises(ValueError, match="already exists"):
            module.create_person(id="mike", name="Mike Again")

    def test_create_person_with_metadata(self, module):
        """Test creating person with optional metadata."""
        person = module.create_person(
            id="mike",
            name="Mike",
            device_trackers=["device_tracker.phone"],
            user_id="ha_user_123",
            picture="/local/mike.jpg",
        )

        assert person.user_id == "ha_user_123"
        assert person.picture == "/local/mike.jpg"

    def test_get_person(self, module):
        """Test getting a person by ID."""
        module.create_person(id="mike", name="Mike")

        person = module.get_person("mike")
        assert person is not None
        assert person.id == "mike"

        nonexistent = module.get_person("nobody")
        assert nonexistent is None

    def test_all_people(self, module):
        """Test getting all people."""
        module.create_person(id="mike", name="Mike")
        module.create_person(id="sarah", name="Sarah")

        people = module.all_people()
        assert len(people) == 2
        assert {p.id for p in people} == {"mike", "sarah"}

    def test_delete_person(self, module):
        """Test deleting a person."""
        module.create_person(id="mike", name="Mike")
        assert module.get_person("mike") is not None

        module.delete_person("mike")
        assert module.get_person("mike") is None

    def test_delete_nonexistent_person_error(self, module):
        """Test deleting nonexistent person raises error."""
        with pytest.raises(ValueError, match="not found"):
            module.delete_person("nobody")


class TestDeviceTrackerManagement:
    """Test device tracker add/remove functionality."""

    @pytest.fixture
    def module(self):
        """Create module with a person."""
        mod = PresenceModule()
        mod.create_person(id="mike", name="Mike", device_trackers=["device_tracker.phone"])
        return mod

    def test_add_device_tracker(self, module):
        """Test adding a device tracker."""
        module.add_device_tracker("mike", "device_tracker.watch")

        person = module.get_person("mike")
        assert "device_tracker.watch" in person.device_trackers
        assert len(person.device_trackers) == 2

    def test_add_device_tracker_with_priority(self, module):
        """Test adding tracker with priority."""
        module.add_device_tracker("mike", "device_tracker.watch", priority=2)

        person = module.get_person("mike")
        assert person.tracker_priority["device_tracker.watch"] == 2

    def test_add_duplicate_tracker(self, module):
        """Test adding duplicate tracker is idempotent."""
        module.add_device_tracker("mike", "device_tracker.phone")

        person = module.get_person("mike")
        assert person.device_trackers.count("device_tracker.phone") == 1

    def test_add_tracker_to_nonexistent_person(self, module):
        """Test adding tracker to nonexistent person raises error."""
        with pytest.raises(ValueError, match="not found"):
            module.add_device_tracker("nobody", "device_tracker.phone")

    def test_remove_device_tracker(self, module):
        """Test removing a device tracker."""
        module.add_device_tracker("mike", "device_tracker.watch")
        module.remove_device_tracker("mike", "device_tracker.watch")

        person = module.get_person("mike")
        assert "device_tracker.watch" not in person.device_trackers

    def test_remove_primary_tracker_updates_primary(self, module):
        """Test removing primary tracker updates primary reference."""
        module.add_device_tracker("mike", "device_tracker.watch")

        # Phone is current primary
        person = module.get_person("mike")
        assert person.primary_tracker == "device_tracker.phone"

        # Remove primary
        module.remove_device_tracker("mike", "device_tracker.phone")

        # Watch becomes new primary
        assert person.primary_tracker == "device_tracker.watch"

    def test_remove_all_trackers_clears_primary(self, module):
        """Test removing all trackers clears primary."""
        module.remove_device_tracker("mike", "device_tracker.phone")

        person = module.get_person("mike")
        assert person.primary_tracker is None
        assert len(person.device_trackers) == 0


class TestLocationQueries:
    """Test location-based queries."""

    @pytest.fixture
    def setup(self):
        """Create module with people and locations."""
        loc_mgr = LocationManager()
        loc_mgr.create_location(id="kitchen", name="Kitchen")
        loc_mgr.create_location(id="office", name="Office")

        bus = EventBus()
        module = PresenceModule()
        module.attach(bus, loc_mgr)

        module.create_person(id="mike", name="Mike")
        module.create_person(id="sarah", name="Sarah")

        return module, loc_mgr

    def test_get_people_in_location_empty(self, setup):
        """Test getting people in empty location."""
        module, _ = setup

        people = module.get_people_in_location("kitchen")
        assert len(people) == 0

    def test_get_people_in_location(self, setup):
        """Test getting people in a location."""
        module, _ = setup

        # Move people to kitchen
        module.move_person("mike", "kitchen")
        module.move_person("sarah", "kitchen")

        people = module.get_people_in_location("kitchen")
        assert len(people) == 2
        assert {p.id for p in people} == {"mike", "sarah"}

    def test_get_person_location(self, setup):
        """Test getting a person's location."""
        module, _ = setup

        # Initially unknown
        assert module.get_person_location("mike") is None

        # Move to kitchen
        module.move_person("mike", "kitchen")
        assert module.get_person_location("mike") == "kitchen"

    def test_get_person_location_nonexistent(self, setup):
        """Test getting location of nonexistent person."""
        module, _ = setup

        assert module.get_person_location("nobody") is None


class TestPersonMovement:
    """Test moving people between locations."""

    @pytest.fixture
    def setup(self):
        """Create module with people and locations."""
        loc_mgr = LocationManager()
        loc_mgr.create_location(id="kitchen", name="Kitchen")
        loc_mgr.create_location(id="office", name="Office")

        bus = EventBus()
        module = PresenceModule()
        module.attach(bus, loc_mgr)

        module.create_person(id="mike", name="Mike")

        return module, loc_mgr, bus

    def test_move_person_to_location(self, setup):
        """Test moving person to a location."""
        module, _, _ = setup

        module.move_person("mike", "kitchen")

        person = module.get_person("mike")
        assert person.current_location_id == "kitchen"

    def test_move_person_to_invalid_location_error(self, setup):
        """Test moving person to nonexistent location raises error."""
        module, _, _ = setup

        with pytest.raises(ValueError, match="Location.*not found"):
            module.move_person("mike", "nonexistent")

    def test_move_person_to_away(self, setup):
        """Test moving person to None (away/unknown)."""
        module, _, _ = setup

        module.move_person("mike", "kitchen")
        module.move_person("mike", None)  # Go away

        person = module.get_person("mike")
        assert person.current_location_id is None

    def test_move_person_emits_event(self, setup):
        """Test that moving person emits presence.changed event."""
        module, _, bus = setup

        events = []
        bus.subscribe(handler=lambda e: events.append(e), event_filter=None)  # Capture all events

        module.move_person("mike", "kitchen")

        assert len(events) == 1
        event = events[0]
        assert event.type == "presence.changed"
        assert event.location_id == "kitchen"
        assert event.payload["person_id"] == "mike"
        assert event.payload["person_name"] == "Mike"
        assert event.payload["from_location"] is None
        assert event.payload["to_location"] == "kitchen"
        assert event.payload["person_entered"] == "mike"

    def test_move_person_no_change_no_event(self, setup):
        """Test moving person to same location doesn't emit event."""
        module, _, bus = setup

        module.move_person("mike", "kitchen")

        events = []
        bus.subscribe(handler=lambda e: events.append(e))

        # Move to same location
        module.move_person("mike", "kitchen")

        assert len(events) == 0

    def test_move_person_between_locations(self, setup):
        """Test moving person from one location to another."""
        module, _, bus = setup

        module.move_person("mike", "kitchen")

        events = []
        bus.subscribe(handler=lambda e: events.append(e))

        module.move_person("mike", "office")

        assert len(events) == 1
        event = events[0]
        assert event.payload["from_location"] == "kitchen"
        assert event.payload["to_location"] == "office"

    def test_move_nonexistent_person_error(self, setup):
        """Test moving nonexistent person raises error."""
        module, _, _ = setup

        with pytest.raises(ValueError, match="Person.*not found"):
            module.move_person("nobody", "kitchen")


class TestStatePersistence:
    """Test state dump and restore."""

    @pytest.fixture
    def module(self):
        """Create module with test data."""
        loc_mgr = LocationManager()
        loc_mgr.create_location(id="kitchen", name="Kitchen")

        bus = EventBus()
        mod = PresenceModule()
        mod.attach(bus, loc_mgr)

        mod.create_person(
            id="mike",
            name="Mike",
            device_trackers=["device_tracker.phone", "device_tracker.watch"],
            user_id="user_123",
        )
        mod.move_person("mike", "kitchen")

        return mod

    def test_dump_state(self, module):
        """Test dumping state to dict."""
        state = module.dump_state()

        assert state["version"] == 1
        assert "mike" in state["people"]

        mike = state["people"]["mike"]
        assert mike["name"] == "Mike"
        assert mike["current_location_id"] == "kitchen"
        assert len(mike["device_trackers"]) == 2
        assert mike["user_id"] == "user_123"

    def test_restore_state(self, module):
        """Test restoring state from dict."""
        # Dump state
        state = module.dump_state()

        # Create new module
        loc_mgr = LocationManager()
        loc_mgr.create_location(id="kitchen", name="Kitchen")
        bus = EventBus()

        new_module = PresenceModule()
        new_module.attach(bus, loc_mgr)

        # Restore state
        new_module.restore_state(state)

        # Verify
        person = new_module.get_person("mike")
        assert person is not None
        assert person.name == "Mike"
        assert person.current_location_id == "kitchen"
        assert len(person.device_trackers) == 2

    def test_restore_invalid_version_ignored(self, module):
        """Test restoring invalid version is ignored."""
        new_module = PresenceModule()
        new_module.attach(EventBus(), LocationManager())

        # Invalid version
        bad_state = {"version": 999, "people": {}}
        new_module.restore_state(bad_state)

        # Should be empty (ignored)
        assert len(new_module.all_people()) == 0


class TestDeviceTrackerEvents:
    """Test device tracker state change handling."""

    @pytest.fixture
    def setup(self):
        """Create module with test setup."""
        loc_mgr = LocationManager()
        loc_mgr.create_location(id="kitchen", name="Kitchen")
        loc_mgr.add_entity_to_location("device_tracker.phone", "kitchen")

        bus = EventBus()
        bus.set_location_manager(loc_mgr)

        module = PresenceModule()
        module.attach(bus, loc_mgr)

        module.create_person(id="mike", name="Mike", device_trackers=["device_tracker.phone"])

        return module, loc_mgr, bus

    def test_device_tracker_updates_person_location(self, setup):
        """Test device tracker state change updates person location."""
        module, loc_mgr, bus = setup

        # Initially unknown
        assert module.get_person_location("mike") is None

        # Simulate device tracker state change
        bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="device_tracker.phone",
                location_id="kitchen",
                payload={"new_state": "kitchen"},
            )
        )

        # Person should now be in kitchen
        assert module.get_person_location("mike") == "kitchen"

    def test_untracked_device_ignored(self, setup):
        """Test untracked device state changes are ignored."""
        module, _, bus = setup

        presence_events = []
        bus.subscribe(
            handler=lambda e: presence_events.append(e) if e.type == "presence.changed" else None
        )

        # Untracked device
        bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="device_tracker.unknown",
                payload={"new_state": "kitchen"},
            )
        )

        # No presence event
        assert len(presence_events) == 0
