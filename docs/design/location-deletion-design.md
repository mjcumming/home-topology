# Location Deletion Design Discussion

**Date**: 2025.01.27  
**Status**: Design Discussion  
**Related**: LocationManager needs `delete_location()` method

---

## Current State

- ❌ **No `delete_location()` method exists** in `LocationManager`
- ⚠️ **TODO in websocket API**: `handle_locations_delete()` needs implementation
- 📝 **Service example exists** in `ha-sync-services.md` but accesses private `_locations` attribute
- 🎯 **UI expects deletion**: Delete button exists in UI design docs

---

## Design Questions

### 1. Child Location Handling

**Question**: What happens to child locations when a parent is deleted?

**Options**:

#### Option A: Prevent Deletion (Safest)
```python
def delete_location(self, location_id: str, cascade: bool = False) -> None:
    children = self.children_of(location_id)
    if children and not cascade:
        raise ValueError(f"Cannot delete location '{location_id}': has {len(children)} children")
```

**Pros**:
- Prevents accidental data loss
- Forces explicit decision
- Clear error message

**Cons**:
- Requires manual cleanup
- More steps for bulk operations

#### Option B: Cascade Delete
```python
def delete_location(self, location_id: str, cascade: bool = True) -> None:
    # Delete all descendants first
    descendants = self.descendants_of(location_id)
    for desc in reversed(descendants):  # Delete children before parents
        self._delete_location_internal(desc.id)
    self._delete_location_internal(location_id)
```

**Pros**:
- Single operation for tree deletion
- Useful for bulk cleanup

**Cons**:
- Dangerous if not careful
- May delete more than intended

#### Option C: Orphan Children
```python
def delete_location(self, location_id: str, orphan_children: bool = False) -> None:
    children = self.children_of(location_id)
    if children:
        if orphan_children:
            # Set parent_id to None (move to Inbox)
            for child in children:
                child.parent_id = None
                child.is_explicit_root = False  # Mark as unassigned
        else:
            raise ValueError(f"Cannot delete: has {len(children)} children")
```

**Pros**:
- Preserves child locations
- Moves them to "Inbox" for reassignment

**Cons**:
- May create many unassigned locations
- Requires manual cleanup

**Recommendation**: **Option A (Prevent) with Option B (Cascade) as opt-in**

```python
def delete_location(
    self, 
    location_id: str, 
    cascade: bool = False,
    orphan_children: bool = False
) -> None:
    """
    Delete a location.
    
    Args:
        location_id: Location to delete
        cascade: If True, delete all descendants first
        orphan_children: If True, move children to Inbox (unassigned)
    
    Raises:
        ValueError: If location doesn't exist or has children (unless cascade/orphan_children)
    """
```

---

### 2. Entity Mapping Cleanup

**Question**: What happens to entities mapped to the location?

**Answer**: **Remove all entity mappings**

```python
# Remove all entity mappings
location = self.get_location(location_id)
if location:
    # Remove from entity_to_location dict
    for entity_id in location.entity_ids.copy():
        if self._entity_to_location.get(entity_id) == location_id:
            del self._entity_to_location[entity_id]
    
    # Clear location's entity list
    location.entity_ids.clear()
```

**Note**: Entities become unmapped (not deleted, just unassigned)

---

### 3. Module Configuration Cleanup

**Question**: What happens to module configs stored in `location.modules`?

**Answer**: **Deleted with location** (automatic, since it's part of Location object)

**Consideration**: Should modules be notified?

```python
# Option: Emit event for modules to clean up
# But LocationManager doesn't have EventBus reference...

# Better: Integration layer handles module notification
# After delete_location(), integration calls:
for module in modules.values():
    if hasattr(module, 'on_location_deleted'):
        module.on_location_deleted(location_id)
```

**Recommendation**: **LocationManager just deletes configs. Integration layer notifies modules.**

---

### 4. Module Runtime State Cleanup

**Question**: What happens to module runtime state (occupancy state, presence tracking, etc.)?

**Answer**: **Modules need cleanup hook**

**Proposed Interface**:

```python
class LocationModule(ABC):
    # ... existing methods ...
    
    def on_location_deleted(self, location_id: str) -> None:
        """
        Called when a location is deleted.
        
        Modules should clean up any runtime state for this location.
        
        Args:
            location_id: The deleted location ID
        """
        pass  # Default: no-op
```

**Module Responsibilities**:

- **OccupancyModule**: Remove location from engine state
- **AutomationModule**: Remove all rules for location
- **PresenceModule**: Move people to "away" (or handle gracefully)
- **AmbientLightModule**: Clear sensor cache and readings

**Implementation Pattern**:

```python
# In integration layer
def delete_location_with_cleanup(location_id: str):
    # 1. Notify modules (cleanup state)
    for module in modules.values():
        if hasattr(module, 'on_location_deleted'):
            module.on_location_deleted(location_id)
    
    # 2. Delete from LocationManager
    loc_mgr.delete_location(location_id, cascade=False)
    
    # 3. Emit event (optional, for UI updates)
    bus.publish(Event(
        type="location.deleted",
        source="integration",
        location_id=location_id,
        payload={},
    ))
```

---

### 5. Parent Reference Handling

**Question**: What if a location references a deleted location as parent?

**Answer**: **Already handled** - `create_location()` validates parent exists, but deletion doesn't update children.

**Current Behavior**: If parent is deleted, children still reference it in `parent_id`. This is fine - `parent_of()` will return `None` for invalid parents.

**Consideration**: Should we validate parent on queries?

```python
def parent_of(self, location_id: str) -> Optional[Location]:
    location = self.get_location(location_id)
    if not location or not location.parent_id:
        return None
    parent = self.get_location(location.parent_id)
    if not parent:
        # Parent was deleted - orphan this location?
        logger.warning(f"Location {location_id} has invalid parent {location.parent_id}")
        return None
    return parent
```

**Recommendation**: **Validate parent exists in queries** (defensive programming)

---

### 6. Event Emission

**Question**: Should LocationManager emit events when locations are deleted?

**Answer**: **No** - LocationManager doesn't have EventBus reference (by design)

**Pattern**: Integration layer emits events after deletion:

```python
# Integration layer
loc_mgr.delete_location(location_id)
bus.publish(Event(
    type="location.deleted",
    source="integration",
    location_id=location_id,
))
```

---

## Proposed Implementation

### LocationManager.delete_location()

```python
def delete_location(
    self,
    location_id: str,
    cascade: bool = False,
    orphan_children: bool = False,
) -> List[str]:
    """
    Delete a location from the topology.
    
    Args:
        location_id: Location ID to delete
        cascade: If True, delete all descendants first (recursive)
        orphan_children: If True, move direct children to Inbox (unassigned)
            Ignored if cascade=True
    
    Returns:
        List of deleted location IDs (for cascade mode)
    
    Raises:
        ValueError: If location doesn't exist
        ValueError: If location has children and neither cascade nor orphan_children is True
    """
    location = self.get_location(location_id)
    if not location:
        raise ValueError(f"Location '{location_id}' does not exist")
    
    deleted_ids = []
    children = self.children_of(location_id)
    
    # Handle children
    if children:
        if cascade:
            # Delete all descendants first (bottom-up)
            descendants = self.descendants_of(location_id)
            for desc in reversed(descendants):  # Children before parents
                deleted_ids.extend(self._delete_location_internal(desc.id))
        elif orphan_children:
            # Move children to Inbox
            for child in children:
                child.parent_id = None
                child.is_explicit_root = False
                logger.info(f"Orphaned child location: {child.id}")
        else:
            raise ValueError(
                f"Cannot delete location '{location_id}': has {len(children)} children. "
                f"Use cascade=True to delete descendants, or orphan_children=True to move children to Inbox."
            )
    
    # Delete the location itself
    deleted_ids.extend(self._delete_location_internal(location_id))
    
    return deleted_ids

def _delete_location_internal(self, location_id: str) -> List[str]:
    """
    Internal method to delete a location (assumes no children).
    
    Returns:
        List containing the deleted location_id
    """
    location = self.get_location(location_id)
    if not location:
        return []
    
    # Remove all entity mappings
    for entity_id in location.entity_ids.copy():
        if self._entity_to_location.get(entity_id) == location_id:
            del self._entity_to_location[entity_id]
            logger.debug(f"Unmapped entity {entity_id} from deleted location {location_id}")
    
    # Delete location
    del self._locations[location_id]
    logger.info(f"Deleted location: {location_id} ({location.name})")
    
    return [location_id]
```

---

### Module Interface Addition

```python
# In modules/base.py
class LocationModule(ABC):
    # ... existing methods ...
    
    def on_location_deleted(self, location_id: str) -> None:
        """
        Called when a location is deleted.
        
        Modules should clean up any runtime state for this location.
        This is called BEFORE the location is removed from LocationManager.
        
        Args:
            location_id: The location ID being deleted
        """
        pass  # Default: no-op, modules override if needed
```

---

### Integration Layer Pattern

```python
def delete_location_with_cleanup(
    location_id: str,
    cascade: bool = False,
    orphan_children: bool = False,
) -> List[str]:
    """
    Delete a location with full cleanup.
    
    This is the integration layer's responsibility:
    1. Notify modules to clean up state
    2. Delete from LocationManager
    3. Emit events
    """
    # 1. Notify modules (cleanup state BEFORE deletion)
    for module in modules.values():
        if hasattr(module, 'on_location_deleted'):
            try:
                module.on_location_deleted(location_id)
            except Exception as e:
                logger.error(f"Error in {module.id}.on_location_deleted({location_id}): {e}")
    
    # 2. Delete from LocationManager
    deleted_ids = loc_mgr.delete_location(
        location_id,
        cascade=cascade,
        orphan_children=orphan_children,
    )
    
    # 3. Emit events for UI updates
    for deleted_id in deleted_ids:
        bus.publish(Event(
            type="location.deleted",
            source="integration",
            location_id=deleted_id,
            payload={},
        ))
    
    return deleted_ids
```

---

## Module-Specific Cleanup Examples

### OccupancyModule

```python
def on_location_deleted(self, location_id: str) -> None:
    """Remove location from occupancy engine."""
    if self._engine and location_id in self._engine.state:
        del self._engine.state[location_id]
        logger.info(f"Removed occupancy state for deleted location: {location_id}")
```

### AutomationModule

```python
def on_location_deleted(self, location_id: str) -> None:
    """Remove all rules for deleted location."""
    if self._engine:
        self._engine.set_location_rules(location_id, [])
        logger.info(f"Removed automation rules for deleted location: {location_id}")
```

### PresenceModule

```python
def on_location_deleted(self, location_id: str) -> None:
    """Move people in deleted location to 'away'."""
    people_in_location = self.get_people_in_location(location_id)
    for person in people_in_location:
        self.move_person(person.id, to_location_id=None)  # Move to away
        logger.info(f"Moved person {person.id} to away (location {location_id} deleted)")
```

### AmbientLightModule

```python
def on_location_deleted(self, location_id: str) -> None:
    """Clear sensor cache and readings for deleted location."""
    if location_id in self._sensor_cache:
        del self._sensor_cache[location_id]
    if location_id in self._last_readings:
        del self._last_readings[location_id]
    logger.info(f"Cleared ambient state for deleted location: {location_id}")
```

---

## Testing Considerations

### Test Cases

1. **Delete leaf location** (no children)
   - ✅ Should succeed
   - ✅ Entities unmapped
   - ✅ Module state cleaned up

2. **Delete location with children** (no cascade)
   - ✅ Should raise ValueError
   - ✅ Nothing deleted

3. **Delete location with cascade=True**
   - ✅ Should delete all descendants
   - ✅ Returns list of deleted IDs
   - ✅ All module states cleaned up

4. **Delete location with orphan_children=True**
   - ✅ Children moved to Inbox
   - ✅ Location deleted
   - ✅ Children preserved

5. **Delete non-existent location**
   - ✅ Should raise ValueError

6. **Module cleanup errors**
   - ✅ Should not prevent deletion
   - ✅ Errors logged

---

## Migration Path

1. **Add `delete_location()` to LocationManager**
2. **Add `on_location_deleted()` to LocationModule base class** (default no-op)
3. **Implement cleanup in each module** (optional, but recommended)
4. **Update integration layer** to call cleanup before deletion
5. **Update websocket API** to use new method
6. **Update service handlers** to use new method
7. **Add tests** for all scenarios

---

## Open Questions

1. **Should we validate parent references on queries?** (defensive programming)
2. **Should LocationManager emit events?** (probably not, keep it simple)
3. **What about location aliases?** (deleted with location, no special handling)
4. **Should we track deletion history?** (probably not, but consider audit log)

---

## Recommendation

**Implement Option A (Prevent) with Option B (Cascade) as opt-in**:

- Default: Prevent deletion if children exist (safest)
- Opt-in cascade: Delete entire subtree
- Opt-in orphan: Move children to Inbox

This provides:
- ✅ Safety by default
- ✅ Flexibility for bulk operations
- ✅ Clear error messages
- ✅ Module cleanup hooks
- ✅ Integration layer pattern

---

**Document Version**: 1.0  
**Status**: Design Discussion  
**Next Steps**: Review and implement

