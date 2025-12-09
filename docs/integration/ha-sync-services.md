# Home Assistant Sync and Services

**Version**: 1.0  
**Date**: 2025.12.09  
**Audience**: Developers building the Home Assistant integration for home-topology

---

## Overview

This document describes how the Home Assistant integration should:

1. **Sync topology** with HA floors and areas
2. **Expose services** for programmatic location management
3. **Provide template functions** for easy ID lookups
4. **Handle conflicts** between HA and home-topology

---

## Table of Contents

1. [Bidirectional Sync Strategy](#bidirectional-sync-strategy)
2. [HA Services](#ha-services)
3. [Template Functions](#template-functions)
4. [Service Examples](#service-examples)
5. [Conflict Resolution](#conflict-resolution)
6. [Implementation Patterns](#implementation-patterns)

---

## Bidirectional Sync Strategy

### Sync Model

The integration maintains **continuous bidirectional sync** between HA and home-topology:

**Inbound (HA → home-topology):**
- HA floors → home-topology locations (as roots)
- HA areas → home-topology locations (as children of floors)
- HA entity area assignments → home-topology entity mappings
- HA aliases → home-topology location aliases

**Outbound (home-topology → HA):**
- User-created locations → optionally create HA areas
- Location hierarchy changes → optionally update HA floor assignments
- Alias changes → optionally update HA aliases

### Initial Import

On first run, import HA's existing structure:

```python
async def initial_import_from_ha(hass, loc_mgr):
    """Import HA floors and areas into home-topology."""
    
    # Import floors as root locations
    floor_registry = floor_reg.async_get(hass)
    for floor in floor_registry.floors.values():
        loc_mgr.create_location(
            id=f"ha_floor_{floor.floor_id}",
            name=floor.name,
            is_explicit_root=True,
            aliases=list(floor.aliases) if floor.aliases else [],
        )
    
    # Import areas as locations
    area_registry = ar.async_get(hass)
    for area in area_registry.areas.values():
        parent_id = None
        if area.floor_id:
            parent_id = f"ha_floor_{area.floor_id}"
        
        loc_mgr.create_location(
            id=f"ha_area_{area.id}",
            name=area.name,
            parent_id=parent_id,
            is_explicit_root=(parent_id is None),  # Root if no floor
            ha_area_id=area.id,
            aliases=list(area.aliases) if area.aliases else [],
        )
    
    # Map entities to locations
    entity_registry = er.async_get(hass)
    for entity in entity_registry.entities.values():
        if entity.area_id:
            try:
                loc_mgr.add_entity_to_location(
                    entity.entity_id,
                    f"ha_area_{entity.area_id}"
                )
            except ValueError:
                _LOGGER.warning(
                    f"Could not map {entity.entity_id} to area {entity.area_id}"
                )
```

### Continuous Sync

Watch for HA changes and update home-topology:

```python
async def setup_ha_watchers(hass, loc_mgr):
    """Watch HA registries for changes."""
    
    area_registry = ar.async_get(hass)
    floor_registry = floor_reg.async_get(hass)
    
    @callback
    def on_area_created(event):
        """Create location when HA area is created."""
        area = area_registry.areas[event.data["area_id"]]
        
        parent_id = None
        if area.floor_id:
            parent_id = f"ha_floor_{area.floor_id}"
        
        try:
            loc_mgr.create_location(
                id=f"ha_area_{area.id}",
                name=area.name,
                parent_id=parent_id,
                is_explicit_root=(parent_id is None),
                ha_area_id=area.id,
                aliases=list(area.aliases) if area.aliases else [],
            )
        except ValueError as e:
            _LOGGER.warning(f"Could not create location from HA area: {e}")
    
    @callback
    def on_area_updated(event):
        """Update location when HA area is updated."""
        area_id = event.data["area_id"]
        area = area_registry.areas[area_id]
        
        location = loc_mgr.get_location(f"ha_area_{area_id}")
        if location:
            # Update name if changed
            if location.name != area.name:
                location.name = area.name
            
            # Update aliases if changed
            ha_aliases = list(area.aliases) if area.aliases else []
            if location.aliases != ha_aliases:
                loc_mgr.set_aliases(location.id, ha_aliases)
            
            # Update parent if floor assignment changed
            new_parent = None
            if area.floor_id:
                new_parent = f"ha_floor_{area.floor_id}"
            
            if location.parent_id != new_parent:
                location.parent_id = new_parent
                location.is_explicit_root = (new_parent is None)
    
    @callback
    def on_area_removed(event):
        """Handle HA area deletion."""
        area_id = event.data["area_id"]
        location_id = f"ha_area_{area_id}"
        
        # Option 1: Delete the location
        # loc_mgr.delete_location(location_id)
        
        # Option 2: Keep it but unlink from HA (recommended)
        location = loc_mgr.get_location(location_id)
        if location:
            location.ha_area_id = None
            location.is_explicit_root = False  # Move to inbox
            location.parent_id = None
    
    # Subscribe to HA registry events
    area_registry.async_subscribe(on_area_created, ar.EVENT_AREA_REGISTRY_CREATED)
    area_registry.async_subscribe(on_area_updated, ar.EVENT_AREA_REGISTRY_UPDATED)
    area_registry.async_subscribe(on_area_removed, ar.EVENT_AREA_REGISTRY_DELETED)
```

---

## HA Services

The integration should expose services for programmatic management:

### Service: `create_location`

Create a new location in home-topology.

```yaml
service: home_topology.create_location
data:
  name: Kitchen Island
  parent_id: kitchen  # Optional
  icon: mdi:counter   # Optional - stored in _meta
  aliases:            # Optional
    - Island
    - Center counter
  floor_id: first_floor  # Optional - link to HA floor
```

**Implementation:**

```python
async def handle_create_location(call):
    """Handle create_location service call."""
    name = call.data["name"]
    parent_id = call.data.get("parent_id")
    icon = call.data.get("icon")
    aliases = call.data.get("aliases", [])
    floor_id = call.data.get("floor_id")
    
    # Generate ID from name
    location_id = slugify(name)
    
    # Create location
    try:
        location = loc_mgr.create_location(
            id=location_id,
            name=name,
            parent_id=parent_id,
            aliases=aliases if isinstance(aliases, list) else [aliases],
        )
        
        # Store icon in metadata if provided
        if icon:
            loc_mgr.set_module_config(
                location_id=location_id,
                module_id="_meta",
                config={"icon": icon}
            )
        
        # Link to HA floor if provided
        if floor_id:
            # Map to HA floor (implementation depends on HA registry APIs)
            pass
        
        _LOGGER.info(f"Created location: {location_id}")
        
    except ValueError as e:
        _LOGGER.error(f"Failed to create location: {e}")
        raise
```

### Service: `delete_location`

Delete a location from home-topology.

```yaml
service: home_topology.delete_location
data:
  location_id: kitchen_island
```

**Implementation:**

```python
async def handle_delete_location(call):
    """Handle delete_location service call."""
    location_id = call.data["location_id"]
    
    # Check if location exists
    location = loc_mgr.get_location(location_id)
    if not location:
        _LOGGER.warning(f"Location '{location_id}' does not exist")
        return
    
    # Check for children
    children = loc_mgr.children_of(location_id)
    if children:
        _LOGGER.error(
            f"Cannot delete location '{location_id}': has {len(children)} children"
        )
        raise ValueError(f"Location has children")
    
    # Remove all entity mappings
    for entity_id in location.entity_ids.copy():
        loc_mgr.remove_entities_from_location([entity_id])
    
    # Delete location
    del loc_mgr._locations[location_id]
    _LOGGER.info(f"Deleted location: {location_id}")
```

### Service: `add_alias_to_location`

Add one or more aliases to a location.

```yaml
service: home_topology.add_alias_to_location
data:
  location_id: living_room
  aliases:
    - Lounge
    - TV room
```

**Implementation:**

```python
async def handle_add_alias_to_location(call):
    """Handle add_alias_to_location service call."""
    location_id = call.data["location_id"]
    aliases = call.data["aliases"]
    
    # Normalize to list
    if isinstance(aliases, str):
        aliases = [aliases]
    
    loc_mgr.add_aliases(location_id, aliases)
```

### Service: `set_location_aliases`

Replace all aliases for a location.

```yaml
service: home_topology.set_location_aliases
data:
  location_id: living_room
  aliases:
    - Lounge
    - TV room
```

### Service: `remove_alias_from_location`

Remove an alias from a location.

```yaml
service: home_topology.remove_alias_from_location
data:
  location_id: living_room
  alias: Lounge
```

### Service: `add_entities_to_location`

Assign multiple entities to a location.

```yaml
service: home_topology.add_entities_to_location
data:
  location_id: kitchen
  entity_id:
    - light.kitchen_main
    - light.kitchen_under_cabinet
    - binary_sensor.kitchen_motion
```

**Implementation:**

```python
async def handle_add_entities_to_location(call):
    """Handle add_entities_to_location service call."""
    location_id = call.data["location_id"]
    entity_ids = call.data["entity_id"]
    
    # Normalize to list
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    
    loc_mgr.add_entities_to_location(entity_ids, location_id)
```

### Service: `remove_entities_from_location`

Remove entities from their current location.

```yaml
service: home_topology.remove_entities_from_location
data:
  entity_id:
    - light.kitchen_main
    - light.kitchen_under_cabinet
```

**Implementation:**

```python
async def handle_remove_entities_from_location(call):
    """Handle remove_entities_from_location service call."""
    entity_ids = call.data["entity_id"]
    
    # Normalize to list
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    
    loc_mgr.remove_entities_from_location(entity_ids)
```

---

## Template Functions

Provide Jinja2 template functions for easy lookups:

### `location_id(name)`

Get location ID from name.

```yaml
# Usage in automations
service: home_topology.add_entities_to_location
data:
  location_id: "{{ location_id('Kitchen') }}"
  entity_id: light.kitchen_main
```

**Implementation:**

```python
def setup_template_functions(hass, loc_mgr):
    """Register template functions."""
    
    def location_id_from_name(name: str) -> str | None:
        """Get location ID from name."""
        location = loc_mgr.get_location_by_name(name)
        return location.id if location else None
    
    def location_id_from_alias(alias: str) -> str | None:
        """Get location ID from alias."""
        location = loc_mgr.find_by_alias(alias)
        return location.id if location else None
    
    # Register with HA's template environment
    hass.data["homeassistant"]["helpers"].template.FUNCTION_ALLOWLIST.add(
        "location_id"
    )
    hass.data["homeassistant"]["helpers"].template.FUNCTION_ALLOWLIST.add(
        "location_from_alias"
    )
    
    # Make available in templates
    template.Template._env.globals["location_id"] = location_id_from_name
    template.Template._env.globals["location_from_alias"] = location_id_from_alias
```

### `location_from_alias(alias)`

Get location ID from alias.

```yaml
service: home_topology.add_alias_to_location
data:
  location_id: "{{ location_from_alias('Lounge') }}"
  alias: TV room
```

---

## Service Examples

### Example 1: Create Party Zone

```yaml
automation:
  - alias: "Create Party Zone"
    trigger:
      - platform: state
        entity_id: input_boolean.party_mode
        to: "on"
    action:
      # Create temporary location
      - service: home_topology.create_location
        data:
          name: "Party Zone"
          parent_id: "{{ location_id('Living Room') }}"
          aliases:
            - Dance Floor
            - DJ Booth
      
      # Add lights to party zone
      - service: home_topology.add_entities_to_location
        data:
          location_id: "{{ location_id('Party Zone') }}"
          entity_id:
            - light.disco_ball
            - light.led_strips
            - light.strobe
```

### Example 2: Reorganize Hierarchy

```yaml
# Move bedroom areas under "Upstairs" floor
automation:
  - alias: "Organize Bedrooms"
    trigger:
      - platform: homeassistant
        event: start
    action:
      - service: home_topology.create_location
        data:
          name: "Upstairs"
          is_explicit_root: true
      
      - service: home_topology.update_location
        data:
          location_id: "{{ location_id('Master Bedroom') }}"
          parent_id: "{{ location_id('Upstairs') }}"
      
      - service: home_topology.update_location
        data:
          location_id: "{{ location_id('Guest Bedroom') }}"
          parent_id: "{{ location_id('Upstairs') }}"
```

### Example 3: Dynamic Aliases for Voice

```yaml
# Add seasonal aliases
automation:
  - alias: "Add Christmas Aliases"
    trigger:
      - platform: template
        value_template: "{{ now().month == 12 }}"
    action:
      - service: home_topology.add_alias_to_location
        data:
          location_id: "{{ location_id('Living Room') }}"
          aliases:
            - Christmas room
            - Tree room
  
  - alias: "Remove Christmas Aliases"
    trigger:
      - platform: template
        value_template: "{{ now().month == 1 }}"
    action:
      - service: home_topology.remove_alias_from_location
        data:
          location_id: "{{ location_id('Living Room') }}"
          alias: Christmas room
      - service: home_topology.remove_alias_from_location
        data:
          location_id: "{{ location_id('Living Room') }}"
          alias: Tree room
```

---

## Conflict Resolution

### Strategies

When HA and home-topology structures diverge, the integration must choose:

**Strategy 1: We Win (Recommended)**
- User changes in home-topology take precedence
- HA changes are imported but don't overwrite user modifications
- Track which locations are "HA-managed" vs "user-managed"

```python
class LocationSyncManager:
    def __init__(self, loc_mgr):
        self.loc_mgr = loc_mgr
        # Track which locations came from HA
        self._ha_managed: set[str] = set()
    
    def mark_ha_managed(self, location_id: str):
        """Mark a location as HA-managed."""
        self._ha_managed.add(location_id)
    
    def is_ha_managed(self, location_id: str) -> bool:
        """Check if location is HA-managed."""
        return location_id in self._ha_managed
    
    def should_sync_from_ha(self, location_id: str) -> bool:
        """Determine if HA changes should overwrite local."""
        # Only sync HA changes for HA-managed locations
        return self.is_ha_managed(location_id)
```

**Strategy 2: Platform Wins**
- Always sync from HA, overwriting user changes
- Simple but frustrating for users
- Not recommended

**Strategy 3: User Decides**
- Show conflicts in UI
- Let user choose which to keep
- Most complex but most flexible

### Recommended Approach

```python
async def sync_area_update(hass, loc_mgr, area_id, sync_mgr):
    """Sync HA area update to home-topology."""
    
    location_id = f"ha_area_{area_id}"
    
    # Only sync if HA-managed
    if not sync_mgr.is_ha_managed(location_id):
        _LOGGER.debug(
            f"Skipping HA sync for user-managed location {location_id}"
        )
        return
    
    # Safe to sync
    area = ar.async_get(hass).areas[area_id]
    location = loc_mgr.get_location(location_id)
    
    if location:
        location.name = area.name
        loc_mgr.set_aliases(location.id, list(area.aliases or []))
```

---

## Implementation Patterns

### Service Registration

```python
# services.yaml
create_location:
  name: Create location
  description: Create a new location in the topology
  fields:
    name:
      name: Name
      description: Name of the location
      required: true
      example: "Kitchen Island"
      selector:
        text:
    parent_id:
      name: Parent
      description: Parent location ID
      required: false
      selector:
        text:
    aliases:
      name: Aliases
      description: Alternative names (for voice assistants)
      required: false
      example: ["Island", "Center counter"]
      selector:
        object:
    icon:
      name: Icon
      description: MDI icon name
      required: false
      example: "mdi:counter"
      selector:
        icon:

delete_location:
  name: Delete location
  description: Delete a location from the topology
  fields:
    location_id:
      name: Location ID
      description: The location to delete
      required: true
      selector:
        text:

add_alias_to_location:
  name: Add alias to location
  description: Add one or more aliases to a location
  fields:
    location_id:
      name: Location ID
      description: The location to modify
      required: true
      selector:
        text:
    aliases:
      name: Aliases
      description: Alias(es) to add
      required: true
      selector:
        object:

set_location_aliases:
  name: Set location aliases
  description: Replace all aliases for a location
  fields:
    location_id:
      name: Location ID
      required: true
      selector:
        text:
    aliases:
      name: Aliases
      description: New list of aliases
      required: true
      selector:
        object:

remove_alias_from_location:
  name: Remove alias from location
  description: Remove an alias from a location
  fields:
    location_id:
      name: Location ID
      required: true
      selector:
        text:
    alias:
      name: Alias
      description: The alias to remove
      required: true
      selector:
        text:

add_entities_to_location:
  name: Add entities to location
  description: Assign entities to a location
  fields:
    location_id:
      name: Location ID
      required: true
      selector:
        text:
    entity_id:
      name: Entities
      description: Entity ID(s) to add
      required: true
      selector:
        entity:
          multiple: true

remove_entities_from_location:
  name: Remove entities from location
  description: Remove entities from their current location
  fields:
    entity_id:
      name: Entities
      description: Entity ID(s) to remove
      required: true
      selector:
        entity:
          multiple: true
```

### Service Handler Registration

```python
async def async_setup_services(hass, loc_mgr):
    """Set up home-topology services."""
    
    async def handle_create_location(call):
        # Implementation above
        pass
    
    async def handle_delete_location(call):
        # Implementation above
        pass
    
    async def handle_add_alias_to_location(call):
        # Implementation above
        pass
    
    # Register all services
    hass.services.async_register(
        DOMAIN, "create_location", handle_create_location
    )
    hass.services.async_register(
        DOMAIN, "delete_location", handle_delete_location
    )
    hass.services.async_register(
        DOMAIN, "add_alias_to_location", handle_add_alias_to_location
    )
    hass.services.async_register(
        DOMAIN, "set_location_aliases", handle_set_location_aliases
    )
    hass.services.async_register(
        DOMAIN, "remove_alias_from_location", handle_remove_alias_from_location
    )
    hass.services.async_register(
        DOMAIN, "add_entities_to_location", handle_add_entities_to_location
    )
    hass.services.async_register(
        DOMAIN, "remove_entities_from_location", handle_remove_entities_from_location
    )
```

---

## Summary

This guide covered:

✅ **Bidirectional sync** - HA ↔ home-topology  
✅ **HA Services** - Programmatic location management  
✅ **Template functions** - Easy ID lookups in automations  
✅ **Service examples** - Real-world automation patterns  
✅ **Conflict resolution** - Handling divergent structures  
✅ **Implementation patterns** - Service registration code  

### Key Principles

1. **HA-managed vs user-managed** - Track origin to avoid conflicts
2. **Continuous sync** - Watch HA registries for changes
3. **Optional outbound sync** - User chooses if changes go to HA
4. **Template functions** - Make automations easy to write
5. **Batch operations** - Efficient multi-entity operations

### Next Steps

- Implement service handlers in HA integration
- Add conflict detection UI
- Document sync behavior for users
- Test with various HA configurations

---

**Document Version**: 1.0  
**Last Updated**: 2025.12.09  
**Status**: Active

