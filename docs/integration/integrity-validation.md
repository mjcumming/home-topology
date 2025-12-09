# Topology Integrity Validation

**Version**: 1.0  
**Date**: 2025.12.09  
**Audience**: Developers building the Home Assistant integration

---

## Overview

This document describes integrity validation patterns for home-topology, ensuring data consistency and detecting topology problems automatically.

---

## Table of Contents

1. [Core Library Validation](#core-library-validation)
2. [HA Integration Repairs](#ha-integration-repairs)
3. [Validation Types](#validation-types)
4. [Auto-Repair Strategies](#auto-repair-strategies)
5. [Implementation Patterns](#implementation-patterns)

---

## Core Library Validation

### IntegrityIssue Data Class

```python
from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class IntegrityIssue:
    """Represents a topology integrity problem."""
    
    type: Literal[
        "broken_parent_reference",
        "circular_reference", 
        "orphaned_entity",
        "duplicate_entity_mapping",
        "missing_required_config",
        "empty_location",
    ]
    location_id: Optional[str] = None
    entity_id: Optional[str] = None
    module_id: Optional[str] = None
    details: str = ""
    severity: Literal["error", "warning", "info"] = "error"
    
    def is_auto_fixable(self) -> bool:
        """Check if this issue can be automatically repaired."""
        return self.type in ["orphaned_entity", "empty_location"]
    
    def get_issue_id(self) -> str:
        """Generate unique issue ID for tracking."""
        parts = [self.type]
        if self.location_id:
            parts.append(self.location_id)
        if self.entity_id:
            parts.append(self.entity_id)
        if self.module_id:
            parts.append(self.module_id)
        return "_".join(parts)
```

### LocationManager Validation Methods

```python
class LocationManager:
    def validate_integrity(self) -> List[IntegrityIssue]:
        """
        Validate topology integrity and return list of issues.
        
        Performs comprehensive checks:
        - Parent references validity
        - Circular reference detection
        - Entity mapping integrity
        - Duplicate entity detection
        - Empty location detection
        
        Returns:
            List of IntegrityIssue objects (empty if all valid)
        """
        issues = []
        
        # Check 1: Broken parent references
        issues.extend(self._check_parent_references())
        
        # Check 2: Circular references
        issues.extend(self._check_circular_references())
        
        # Check 3: Orphaned entities
        issues.extend(self._check_orphaned_entities())
        
        # Check 4: Duplicate entity mappings
        issues.extend(self._check_duplicate_entities())
        
        # Check 5: Empty locations
        issues.extend(self._check_empty_locations())
        
        return issues
    
    def _check_parent_references(self) -> List[IntegrityIssue]:
        """Check that all parent_id references point to existing locations."""
        issues = []
        
        for location in self.all_locations():
            if location.parent_id and location.parent_id not in self._locations:
                issues.append(IntegrityIssue(
                    type="broken_parent_reference",
                    location_id=location.id,
                    details=f"Parent '{location.parent_id}' does not exist",
                    severity="error"
                ))
        
        return issues
    
    def _check_circular_references(self) -> List[IntegrityIssue]:
        """Check for circular parent-child relationships."""
        issues = []
        
        for location in self.all_locations():
            try:
                ancestors = self.ancestors_of(location.id)
                # Check if location appears in its own ancestry
                if any(anc.id == location.id for anc in ancestors):
                    issues.append(IntegrityIssue(
                        type="circular_reference",
                        location_id=location.id,
                        details="Location is its own ancestor (circular reference)",
                        severity="error"
                    ))
            except RecursionError:
                issues.append(IntegrityIssue(
                    type="circular_reference",
                    location_id=location.id,
                    details="Infinite loop detected in parent chain",
                    severity="error"
                ))
        
        return issues
    
    def _check_orphaned_entities(self) -> List[IntegrityIssue]:
        """Check for entities mapped to non-existent locations."""
        issues = []
        
        for entity_id, location_id in self._entity_to_location.items():
            if location_id not in self._locations:
                issues.append(IntegrityIssue(
                    type="orphaned_entity",
                    entity_id=entity_id,
                    location_id=location_id,
                    details=f"Entity mapped to non-existent location '{location_id}'",
                    severity="warning"
                ))
        
        return issues
    
    def _check_duplicate_entities(self) -> List[IntegrityIssue]:
        """Check for entities appearing in multiple locations."""
        issues = []
        
        # Build reverse mapping: entity_id -> list of locations
        entity_locations = {}
        for location in self.all_locations():
            for entity_id in location.entity_ids:
                if entity_id not in entity_locations:
                    entity_locations[entity_id] = []
                entity_locations[entity_id].append(location.id)
        
        # Find duplicates
        for entity_id, location_ids in entity_locations.items():
            if len(location_ids) > 1:
                issues.append(IntegrityIssue(
                    type="duplicate_entity_mapping",
                    entity_id=entity_id,
                    details=f"Entity appears in multiple locations: {', '.join(location_ids)}",
                    severity="error"
                ))
        
        return issues
    
    def _check_empty_locations(self) -> List[IntegrityIssue]:
        """Check for locations with no entities and no children."""
        issues = []
        
        for location in self.all_locations():
            # Skip roots and locations with children
            if location.is_explicit_root or self.children_of(location.id):
                continue
            
            # Check if truly empty (no entities, no module config)
            if not location.entity_ids and not location.modules:
                issues.append(IntegrityIssue(
                    type="empty_location",
                    location_id=location.id,
                    details="Location has no entities, children, or configuration",
                    severity="info"
                ))
        
        return issues
    
    def auto_repair(self, issue: IntegrityIssue) -> bool:
        """
        Attempt to automatically repair an integrity issue.
        
        Args:
            issue: The issue to repair
        
        Returns:
            True if successfully repaired, False if manual intervention needed
        """
        if issue.type == "orphaned_entity" and issue.entity_id:
            # Remove invalid entity mapping
            if issue.entity_id in self._entity_to_location:
                del self._entity_to_location[issue.entity_id]
                logger.info(f"Auto-repaired: Removed orphaned entity {issue.entity_id}")
                return True
        
        elif issue.type == "duplicate_entity_mapping" and issue.entity_id:
            # Keep entity in first location found, remove from others
            # This is conservative - user may want different behavior
            for location in self.all_locations():
                if issue.entity_id in location.entity_ids:
                    # Keep in this location, remove from all others
                    for other_location in self.all_locations():
                        if other_location.id != location.id and issue.entity_id in other_location.entity_ids:
                            other_location.entity_ids.remove(issue.entity_id)
                    logger.info(f"Auto-repaired: Kept {issue.entity_id} in {location.id} only")
                    return True
        
        elif issue.type == "empty_location" and issue.location_id:
            # Delete empty location
            if issue.location_id in self._locations:
                del self._locations[issue.location_id]
                logger.info(f"Auto-repaired: Deleted empty location {issue.location_id}")
                return True
        
        # Cannot auto-repair other issue types
        return False
```

---

## HA Integration Repairs

### Setup Repair Detection

```python
from homeassistant.helpers import issue_registry as ir

async def async_setup_integrity_monitoring(hass, loc_mgr):
    """Set up continuous integrity monitoring with HA repairs."""
    
    async def check_and_report_issues():
        """Run integrity check and create/update repair issues."""
        
        # Validate topology
        issues = loc_mgr.validate_integrity()
        
        # Track current issue IDs
        current_issue_ids = {issue.get_issue_id() for issue in issues}
        
        # Create/update repair issues
        for issue in issues:
            issue_id = issue.get_issue_id()
            
            # Map severity
            severity = (
                ir.IssueSeverity.ERROR if issue.severity == "error"
                else ir.IssueSeverity.WARNING if issue.severity == "warning"
                else ir.IssueSeverity.INFO
            )
            
            # Create repair issue
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=issue.is_auto_fixable(),
                severity=severity,
                translation_key=f"topology_{issue.type}",
                translation_placeholders={
                    "location_id": issue.location_id or "N/A",
                    "entity_id": issue.entity_id or "N/A",
                    "details": issue.details,
                },
            )
        
        # Remove resolved issues
        # (HA will auto-remove if issue ID no longer created)
    
    # Run check on startup
    await check_and_report_issues()
    
    # Schedule periodic checks (every hour)
    async_track_time_interval(
        hass,
        lambda _: hass.async_create_task(check_and_report_issues()),
        timedelta(hours=1),
    )
```

### Repair Issue Translations

```yaml
# strings.json (HA integration)
{
  "issues": {
    "topology_broken_parent_reference": {
      "title": "Broken Parent Reference in Topology",
      "description": "Location `{location_id}` references a parent that doesn't exist: {details}"
    },
    "topology_circular_reference": {
      "title": "Circular Reference in Topology",
      "description": "Location `{location_id}` creates a circular reference: {details}"
    },
    "topology_orphaned_entity": {
      "title": "Orphaned Entity Mapping",
      "description": "Entity `{entity_id}` is mapped to non-existent location: {details}\n\nThis can be automatically fixed."
    },
    "topology_duplicate_entity_mapping": {
      "title": "Duplicate Entity in Multiple Locations",
      "description": "Entity `{entity_id}` appears in multiple locations: {details}"
    },
    "topology_empty_location": {
      "title": "Empty Location Found",
      "description": "Location `{location_id}` has no entities or children: {details}\n\nThis can be automatically cleaned up."
    }
  }
}
```

### Auto-Repair Service

```python
async def handle_auto_repair(call):
    """Handle auto-repair service call."""
    
    kernel = hass.data[DOMAIN]
    loc_mgr = kernel["loc_mgr"]
    
    # Get all issues
    issues = loc_mgr.validate_integrity()
    
    # Attempt auto-repair
    repaired = []
    failed = []
    
    for issue in issues:
        if issue.is_auto_fixable():
            if loc_mgr.auto_repair(issue):
                repaired.append(issue.get_issue_id())
                # Remove repair issue from HA
                ir.async_delete_issue(hass, DOMAIN, issue.get_issue_id())
            else:
                failed.append(issue.get_issue_id())
    
    # Return results
    return {
        "repaired": repaired,
        "failed": failed,
        "total_issues": len(issues),
    }

# Register service
hass.services.async_register(
    DOMAIN,
    "auto_repair_topology",
    handle_auto_repair,
    schema=vol.Schema({}),
)
```

---

## Validation Types

### 1. Broken Parent Reference

**What**: Location references a parent that doesn't exist

**Severity**: Error

**Auto-fixable**: No (requires user decision - make root or assign new parent)

**Example**:
```
Location: kitchen
Parent: main_floor (DOES NOT EXIST)
```

**User Actions**:
- Delete the location
- Make it a root location
- Assign a different parent

---

### 2. Circular Reference

**What**: Location appears in its own ancestry chain

**Severity**: Error

**Auto-fixable**: No (complex graph manipulation required)

**Example**:
```
house → main_floor → kitchen → house (CIRCULAR!)
```

**User Actions**:
- Break the circular chain by changing parent

---

### 3. Orphaned Entity

**What**: Entity mapped to location that doesn't exist

**Severity**: Warning

**Auto-fixable**: Yes (remove invalid mapping)

**Example**:
```
Entity: light.kitchen
Mapped to: kitchen (DOES NOT EXIST)
```

**Auto-repair**: Remove entity mapping

---

### 4. Duplicate Entity Mapping

**What**: Entity appears in multiple locations' entity lists

**Severity**: Error

**Auto-fixable**: Partial (keep in first location, remove from others)

**Example**:
```
Entity: light.shared
In: kitchen.entity_ids AND dining_room.entity_ids
```

**Auto-repair**: Keep in first location only

---

### 5. Empty Location

**What**: Location has no entities, no children, no configuration

**Severity**: Info

**Auto-fixable**: Yes (delete location)

**Example**:
```
Location: unused_room
Entities: []
Children: []
Modules: {}
```

**Auto-repair**: Delete location

---

## Auto-Repair Strategies

### Safe Auto-Repairs

These can be performed automatically without risk:

1. **Orphaned entities** → Remove invalid mappings
2. **Empty locations** → Delete unused locations
3. **Duplicate entities** → Keep in first location only (conservative)

### Manual Intervention Required

These require user decision:

1. **Broken parent references** → User chooses: delete, make root, or reassign
2. **Circular references** → User breaks the cycle
3. **Missing module dependencies** → User reconfigures

---

## Implementation Patterns

### Pattern 1: Startup Validation

Run integrity check on HA startup:

```python
async def async_setup_entry(hass, entry):
    """Set up home-topology."""
    
    # ... create kernel ...
    
    # Validate integrity
    issues = loc_mgr.validate_integrity()
    
    if issues:
        _LOGGER.warning(f"Found {len(issues)} topology integrity issues")
        for issue in issues:
            _LOGGER.warning(f"  - {issue.type}: {issue.details}")
        
        # Create repair issues
        for issue in issues:
            ir.async_create_issue(...)
    else:
        _LOGGER.info("Topology integrity: OK")
```

### Pattern 2: Periodic Validation

Check integrity regularly:

```python
# Every hour
async_track_time_interval(
    hass,
    lambda _: hass.async_create_task(validate_and_report()),
    timedelta(hours=1),
)
```

### Pattern 3: On-Demand Validation

Service for manual checks:

```yaml
service: home_topology.validate_integrity
# Returns list of issues
```

### Pattern 4: Auto-Repair on Save

Validate and auto-repair when saving configuration:

```python
async def save_topology_config(loc_mgr):
    """Save topology config with auto-repair."""
    
    # Validate
    issues = loc_mgr.validate_integrity()
    
    # Auto-repair what we can
    for issue in issues:
        if issue.is_auto_fixable():
            loc_mgr.auto_repair(issue)
    
    # Re-validate
    remaining_issues = loc_mgr.validate_integrity()
    
    # Save
    await async_save_to_store(...)
    
    return {
        "repaired": len(issues) - len(remaining_issues),
        "remaining": len(remaining_issues),
    }
```

---

## Services

### `home_topology.validate_integrity`

Manually trigger integrity validation.

```yaml
service: home_topology.validate_integrity
# Returns: { "issues": [...], "count": N }
```

### `home_topology.auto_repair_topology`

Automatically fix all auto-fixable issues.

```yaml
service: home_topology.auto_repair_topology
# Returns: { "repaired": [...], "failed": [...], "total_issues": N }
```

---

## Automation Examples

### Daily Health Check

```yaml
automation:
  - alias: "Daily Topology Health Check"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: home_topology.validate_integrity
      - service: persistent_notification.create
        data:
          title: "Topology Health Check"
          message: >
            Found {{ result.count }} integrity issues.
            {% if result.count > 0 %}
            Check repair issues for details.
            {% endif %}
```

### Auto-Repair on Startup

```yaml
automation:
  - alias: "Auto-Repair Topology on Startup"
    trigger:
      - platform: homeassistant
        event: start
    action:
      - delay: 00:01:00  # Wait for full startup
      - service: home_topology.auto_repair_topology
```

---

## Testing

### Unit Tests

```python
def test_validate_broken_parent():
    """Test detection of broken parent references."""
    mgr = LocationManager()
    
    # Create location with invalid parent
    loc = Location(
        id="kitchen",
        name="Kitchen",
        parent_id="nonexistent"
    )
    mgr._locations["kitchen"] = loc
    
    # Validate
    issues = mgr.validate_integrity()
    
    assert len(issues) == 1
    assert issues[0].type == "broken_parent_reference"
    assert issues[0].location_id == "kitchen"
```

---

## Summary

Integrity validation provides:

✅ **Automated problem detection** - Find issues before they cause problems  
✅ **Self-healing capabilities** - Auto-fix common issues  
✅ **User visibility** - HA repair system integration  
✅ **Data consistency** - Ensure topology stays valid  
✅ **Peace of mind** - Continuous monitoring  

---

**Document Version**: 1.0  
**Last Updated**: 2025.12.09  
**Status**: Proposed Feature

