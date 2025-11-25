# Home Topology UI Design Specification v0.1

> This document defines the UI design for the Home Topology Location Manager. It will be used to drive UI implementation in the Home Assistant integration.

**Status**: Draft (Prototyping in Gemini Canvas)  
**Last Updated**: 2025-11-25  
**Target Platform**: Home Assistant Panel (standalone view)

---

## 1. Overview

### 1.1 Purpose

The Location Manager UI provides a visual interface for:
- **Modeling** the spatial topology of a home (floors, rooms, zones)
- **Configuring** behavior modules attached to locations (Occupancy, Actions)
- **Managing** entity-to-location assignments
- **Visualizing** location state (occupied, vacant, etc.)

### 1.2 UI Type

This is a **standalone panel** in Home Assistant (similar to Energy Dashboard or History), not a Lovelace card. Rationale:
- Complex hierarchical data requires dedicated screen space
- Configuration workflows need persistent UI state
- Not suitable for dashboard embedding

### 1.3 Design Principles

1. **Tree-first navigation** - Locations are the primary object; modules attach to them
2. **Progressive disclosure** - Show overview first, details on selection
3. **Direct manipulation** - Drag-and-drop for reordering, inline editing
4. **Visual hierarchy** - Icons and indentation communicate structure

---

## 2. Layout Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Logo] Location Manager    [Undo] [Redo]    [Code/Preview] [Share] │  <- Header
├───────────────────────────────────┬─────────────────────────────────┤
│                                   │                                 │
│  Home Topology                    │  [Icon] Location Name           │
│  Model your space...              │  location-id                    │
│                                   │                                 │
│  [+ New Location] [Save Changes]  │  [Occupancy] [Actions]          │
│                                   │                                 │
│  ┌─ First Floor                   │  ─────────────────────────────  │
│  │  ├─ Kitchen ←(selected)        │  PRESENCE LOGIC         [ON]   │
│  │  ├─ Living Room                │                                 │
│  │  ├─ Dining Room                │  Default Timeout    [10] min    │
│  │  └─ Office                     │  Wasp-in-a-Box       [ ]        │
│  │                                │                                 │
│  ├─ Second Floor                  │  ─────────────────────────────  │
│  │  ├─ Master Suite               │  INPUT TRIGGERS                 │
│  │  │  ├─ Master Bedroom          │                                 │
│  │  │  ├─ Master Bath             │  ⊙ Kitchen Motion    [1 Rules]  │
│  │  │  └─ Master Closet           │                                 │
│  │  └─ Kids Wing                  │                                 │
│  │                                │                                 │
│  ├─ Basement                      │                                 │
│  │                                │                                 │
│  └─ Outdoor                       │                                 │
│     ├─ Back Patio                 │                                 │
│     └─ Garage                     │                                 │
│                                   │                                 │
└───────────────────────────────────┴─────────────────────────────────┘
        Tree Panel (~40%)                 Details Panel (~60%)
```

### 2.1 Panel Dimensions

| Panel | Width | Purpose |
|-------|-------|---------|
| Tree Panel | ~40% (min 300px) | Location hierarchy browser |
| Details Panel | ~60% (min 400px) | Selected location configuration |

### 2.2 Responsive Behavior

- **Desktop (>1024px)**: Side-by-side panels
- **Tablet (768-1024px)**: Collapsible tree, details takes full width
- **Mobile (<768px)**: Stack vertically, tree as drawer

---

## 3. Component Specifications

### 3.1 Tree Panel

#### 3.1.1 Header Section

```
Home Topology
Model your space and attach behavior modules.

[+ New Location]  [Save Changes]
```

| Element | Type | Behavior |
|---------|------|----------|
| Title | Static text | "Home Topology" |
| Subtitle | Static text | "Model your space and attach behavior modules." |
| + New Location | Button (outline) | Opens location creation dialog |
| Save Changes | Button (primary) | Persists all pending changes |

#### 3.1.2 Tree Node Structure

Each tree node displays:

```
[Drag] [Expand] [Icon] Location Name                    [Delete] [Status]
```

| Element | Description |
|---------|-------------|
| Drag Handle | 6-dot grip icon, visible on hover |
| Expand/Collapse | Chevron, only if has children |
| Type Icon | Indicates location type (see 3.1.3) |
| Location Name | Editable on double-click |
| Delete Button | ⊗ icon, visible on hover |
| Status Indicator | Optional spark/dot for state |

#### 3.1.3 Location Type Icons

| Type | Icon | Description |
|------|------|-------------|
| Floor | ≡ (layers) | A floor/level of the building |
| Room | ◎ (target) | Standard room |
| Zone | ◇ (diamond) | Sub-room area |
| Suite | ❖ (4-diamond) | Room group (e.g., Master Suite) |
| Outdoor | ⌂ (house outline) | Exterior location |
| Building | ▣ (building) | Separate structure (garage, shed) |

> **Note**: Icon set TBD. Will use Material Design Icons or similar.

#### 3.1.4 Tree Interactions

| Action | Trigger | Result |
|--------|---------|--------|
| Select | Click node | Highlights node, loads details panel |
| Expand/Collapse | Click chevron | Shows/hides children |
| Rename | Double-click name | Inline text edit |
| Reorder | Drag handle | Moves node within parent |
| Reparent | Drag to different parent | Changes parent_id |
| Delete | Click ⊗ | Confirmation dialog, removes location |
| Add Child | Right-click → Add Child | Creates child location |

#### 3.1.5 Tree State Indicators

| Indicator | Meaning |
|-----------|---------|
| Blue highlight | Currently selected |
| Spark icon (✦) | Has pending changes |
| Dot (colored) | Occupancy state (green=occupied, gray=vacant) |
| Italic text | Location is locked |

---

### 3.2 Details Panel

The details panel shows configuration for the selected location.

#### 3.2.1 Header Section

```
[Type Icon]  Location Name
             location-id

[Occupancy]  [Actions]
```

| Element | Description |
|---------|-------------|
| Type Icon | Large icon matching tree node type |
| Location Name | Display name (editable via tree) |
| Location ID | Slug/identifier (e.g., "room-kitchen") |
| Module Tabs | Switch between Occupancy, Actions, (future: Comfort, Energy) |

#### 3.2.2 Occupancy Tab

```
PRESENCE LOGIC                                    [Toggle: ON/OFF]
─────────────────────────────────────────────────────────────────
Default Timeout             [Input: 10] min
Wasp-in-a-Box              [Checkbox: unchecked]

INPUT TRIGGERS
─────────────────────────────────────────────────────────────────
⊙ Kitchen Motion                                  [1 Rules]
⊙ Kitchen Door Contact                            [2 Rules]
```

##### Presence Logic Section

| Field | Type | Maps To | Description |
|-------|------|---------|-------------|
| Presence Logic Toggle | Switch | `modules.occupancy.enabled` | Enable/disable occupancy tracking |
| Default Timeout | Number input | `modules.occupancy.timeout` | Minutes before marking vacant |
| Wasp-in-a-Box | Checkbox | `modules.occupancy.wasp_mode` | Enable wasp-in-a-box algorithm |

##### Input Triggers Section

Lists entities assigned to this location that trigger occupancy events.

| Element | Description |
|---------|-------------|
| Entity Icon | Entity domain icon (motion, door, etc.) |
| Entity Name | Friendly name |
| Rules Badge | Count of rules attached to this trigger |

**Clicking a trigger** expands to show/edit rules (future iteration).

#### 3.2.3 Actions Tab

```
AUTOMATION RULES
─────────────────────────────────────────────────────────────────
[+ Add Rule]

Rule: "Turn on lights when occupied"              [Edit] [Delete]
  Trigger: Occupancy → Occupied
  Action: light.kitchen → turn_on

Rule: "Turn off lights when vacant"               [Edit] [Delete]
  Trigger: Occupancy → Vacant (after 5 min)
  Action: light.kitchen → turn_off
```

> **Note**: Actions tab design is preliminary. Full spec pending ActionsModule implementation.

---

## 4. Data Model Mapping

The UI maps directly to the home-topology data structures.

### 4.1 Location → Tree Node

```python
# From core/location.py
@dataclass
class Location:
    id: str                      # → node identifier
    name: str                    # → node display text
    parent_id: Optional[str]     # → tree hierarchy
    is_explicit_root: bool       # → root vs unassigned styling
    ha_area_id: Optional[str]    # → (future) HA area link indicator
    entity_ids: List[str]        # → triggers list in details
    modules: Dict[str, Dict]     # → module tab configurations
```

### 4.2 Module Config → Details Panel

```python
# modules.occupancy blob
{
    "enabled": True,              # → Presence Logic toggle
    "timeout": 600,               # → Default Timeout (seconds, display as minutes)
    "wasp_mode": False,           # → Wasp-in-a-Box checkbox
    "strategy": "inherit",        # → (future) strategy selector
}
```

### 4.3 API Endpoints (Conceptual)

| Action | Method | Endpoint |
|--------|--------|----------|
| Get all locations | GET | `/api/home_topology/locations` |
| Create location | POST | `/api/home_topology/locations` |
| Update location | PUT | `/api/home_topology/locations/{id}` |
| Delete location | DELETE | `/api/home_topology/locations/{id}` |
| Reorder locations | PATCH | `/api/home_topology/locations/reorder` |
| Get location state | GET | `/api/home_topology/locations/{id}/state` |

---

## 5. Interaction Flows

### 5.1 Create New Location

```
1. User clicks [+ New Location]
2. Dialog appears:
   - Name: [text input]
   - Type: [dropdown: Floor/Room/Zone/Suite/Outdoor/Building]
   - Parent: [dropdown: existing locations or "Root"]
3. User fills form, clicks [Create]
4. New location appears in tree, selected
5. Details panel shows default module configs
```

### 5.2 Configure Occupancy

```
1. User selects location in tree
2. Details panel loads, Occupancy tab active
3. User toggles Presence Logic ON
4. User sets timeout to 15 minutes
5. [Save Changes] button becomes active
6. User clicks [Save Changes]
7. Changes persisted, spark indicator clears
```

### 5.3 Drag and Drop Reordering

```
1. User hovers over location, drag handle appears
2. User drags location
3. Drop zones highlight:
   - Between siblings (reorder)
   - Over parent node (reparent)
4. User drops
5. Tree updates, [Save Changes] activates
```

#### 5.3.1 Hierarchy Constraints

While the core kernel is type-agnostic (any location can parent any other), the UI enforces **sensible hierarchy rules** to prevent nonsensical topologies.

##### Location Type Hierarchy

```
Building/Outdoor (root level only)
    └── Floor
            └── Room / Suite
                    └── Zone (terminal, no children)

Suite is a special case:
    └── Suite
            └── Room (e.g., Master Suite → Master Bedroom, Master Bath)
                    └── Zone
```

##### Valid Parent → Child Relationships

| Parent Type | Can Contain |
|-------------|-------------|
| **Root** | Floor, Building, Outdoor |
| **Floor** | Room, Suite |
| **Suite** | Room only |
| **Room** | Zone only |
| **Zone** | Nothing (terminal) |
| **Building** | Floor, Room |
| **Outdoor** | Zone only |

##### Illegal Moves (UI must block these)

| Attempted Move | Allowed? | Reason |
|----------------|----------|--------|
| Floor → Room | ❌ No | Floors contain rooms, not vice versa |
| Floor → Floor | ❌ No | Floors are siblings, not nested |
| Room → Room | ❌ No | Rooms are flat within a floor (use Suite for grouping) |
| Room → Zone | ❌ No | Zones are sub-divisions, cannot contain rooms |
| Zone → anything | ❌ No | Zones are terminal nodes |
| Suite → Floor | ❌ No | Suites exist within floors |
| Room → Suite | ✅ Yes | Suites can contain rooms (Master Suite → Bedroom) |
| Zone → Room | ✅ Yes | Zones belong inside rooms |
| Outdoor → Building | ❌ No | These are both root-level |
| Anything → itself | ❌ No | Cannot be own parent |
| Parent → descendant | ❌ No | Cannot create cycles |

##### Drag Feedback for Illegal Moves

| State | Visual Feedback |
|-------|-----------------|
| Valid drop target | Green highlight, "+" cursor |
| Invalid drop target | Red highlight, "🚫" cursor, tooltip: "Cannot place {type} inside {type}" |
| Dragging over self | No highlight |
| Dragging over descendant | Red highlight, tooltip: "Cannot move into own child" |

##### Edge Cases

1. **Converting types**: If user changes a Room to a Floor, check if current parent is valid. If not, prompt to move first.
2. **Orphaned children**: If a Suite is deleted, its child Rooms become children of the Suite's parent Floor.
3. **Root demotion**: Cannot drag a Floor into another Floor. Must create hierarchy properly.

> **Note**: These constraints are UI-enforced. The core `LocationManager` accepts any valid tree structure. This allows power users to bypass via API if needed, while the UI guides normal users toward sensible hierarchies.

##### Type Storage

Location types are **not stored in the kernel**. The integration layer is responsible for:

1. **Storing type metadata** - Either in integration's own registry or in `modules["_meta"]`
2. **Enforcing hierarchy rules** - Validating moves before committing
3. **Providing type icons** - Mapping type → icon for tree display

```python
# Recommended: Use _meta module for type storage
meta = loc_mgr.get_module_config(location_id, "_meta") or {}
location_type = meta.get("type", "room")  # Default to room
```

> **See also**: [Integration Guide](../integration-guide.md#location-types-your-responsibility) for implementation patterns.

---

## 6. Visual Design Tokens

> Placeholder values. Will align with Home Assistant theme variables.

### 6.1 Colors

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| `--primary` | #1976D2 | #90CAF9 | Selected state, primary buttons |
| `--surface` | #FFFFFF | #1E1E1E | Panel backgrounds |
| `--on-surface` | #212121 | #E0E0E0 | Text |
| `--border` | #E0E0E0 | #424242 | Dividers, borders |
| `--occupied` | #4CAF50 | #81C784 | Occupied indicator |
| `--vacant` | #9E9E9E | #757575 | Vacant indicator |
| `--locked` | #FF9800 | #FFB74D | Locked indicator |

### 6.2 Typography

| Element | Size | Weight |
|---------|------|--------|
| Panel title | 20px | 600 |
| Section header | 12px | 600 (uppercase) |
| Tree node | 14px | 400 |
| Location ID | 12px | 400 (muted) |

### 6.3 Spacing

| Token | Value |
|-------|-------|
| `--spacing-xs` | 4px |
| `--spacing-sm` | 8px |
| `--spacing-md` | 16px |
| `--spacing-lg` | 24px |
| Tree indent | 24px per level |

---

## 7. State Management

### 7.1 UI State (Local)

| State | Type | Description |
|-------|------|-------------|
| `selectedLocationId` | string | Currently selected location |
| `expandedNodes` | Set<string> | Which tree nodes are expanded |
| `pendingChanges` | Map<string, Location> | Unsaved modifications |
| `activeTab` | 'occupancy' \| 'actions' | Current module tab |

### 7.2 Server State

| State | Source | Description |
|-------|--------|-------------|
| `locations` | API | Full location tree |
| `occupancyStates` | WebSocket | Real-time occupancy per location |
| `moduleConfigs` | API | Per-location module configurations |

### 7.3 Sync Strategy

- **Load**: Fetch full tree on panel open
- **Optimistic updates**: Update UI immediately, rollback on error
- **Save**: Batch pending changes on [Save Changes]
- **Real-time**: WebSocket for occupancy state updates only

---

## 8. Accessibility

### 8.1 Keyboard Navigation

| Key | Action |
|-----|--------|
| Arrow Up/Down | Move selection in tree |
| Arrow Right | Expand node / enter children |
| Arrow Left | Collapse node / go to parent |
| Enter | Activate selected (edit, open) |
| Delete | Delete selected (with confirmation) |
| Tab | Move between panels |

### 8.2 Screen Reader

- Tree uses `role="tree"` and `role="treeitem"`
- Expanded state announced via `aria-expanded`
- Selection announced via `aria-selected`
- Occupancy state included in accessible name

### 8.3 Focus Management

- Focus trapped in dialogs
- Focus returns to trigger on dialog close
- Visible focus indicator on all interactive elements

---

## 9. Future Considerations

### 9.1 Entity Inbox

Unassigned entities (discovered but not placed in topology):

```
INBOX (3 entities)
─────────────────────────────────────────────────────────────────
⊙ binary_sensor.garage_motion              [Assign to Location ▼]
⊙ sensor.outdoor_temperature               [Assign to Location ▼]
⊙ light.unknown_switch_1                   [Assign to Location ▼]
```

### 9.2 Bulk Operations

- Multi-select locations for bulk config
- Copy/paste module configs between locations
- Import/export topology as YAML

### 9.3 Visualization Modes

- **Tree view** (current): Hierarchical list
- **Floor plan view**: 2D spatial layout
- **Graph view**: Visual hierarchy with connections

---

## 10. Implementation Notes

### 10.1 Technology Stack (TBD)

Options for HA panel implementation:
- **Lit Element**: HA native, consistent with core UI
- **React**: Easier development, requires bundling
- **Preact**: React-compatible, smaller bundle

### 10.2 HA Integration Points

| Integration | Method |
|-------------|--------|
| Panel registration | `async_register_panel()` |
| State updates | WebSocket API |
| Configuration | Config flow + options flow |
| Services | `home_topology.create_location`, etc. |

### 10.3 Development Workflow

1. Prototype in Gemini Canvas (current phase)
2. Document design in this spec (current phase)
3. Create HA integration repository
4. Implement panel using Lit Element
5. Iterate based on user testing

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2025-11-25 | Initial draft from Gemini Canvas mockup |

---

**Status**: Draft  
**Owner**: Mike  
**Next Review**: After Gemini Canvas iteration

