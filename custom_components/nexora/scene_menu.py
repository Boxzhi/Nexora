"""Validated presentation overlay over immutable registered capabilities."""
from dataclasses import dataclass
from .business_model import MAX_MENU_QUERIES, STOP_CONDITIONS, BusinessRegistry
from .menu import Item, ID, RESERVED

@dataclass(frozen=True)
class SceneSpec:
    members: tuple
    anchor: str = ""
    supplements: tuple = ()
    stop_on: tuple = ()

@dataclass(frozen=True)
class Node:
    id: str
    parent: str
    name: str
    order: int
    members: tuple = ()
    anchor: str = ""
    supplements: tuple = ()
    stop_on: tuple = ()
    alias_of: str = ""

def install(menu,rows):
    if menu.scenes:
        raise ValueError("scene layout already installed")
    registry=BusinessRegistry(menu.capabilities)
    items=dict(menu.items)
    children=dict(menu.children)
    aliases={}
    specs={}
    root="scene"
    items[root]=Item(root,items["root"].name,"",0,"menu")
    # Validate the complete projection before updating the existing menu.
    for row in rows:
        if not ID.fullmatch(row.id) or not row.id.startswith("scene.") or row.id in items or row.parent not in items or not row.parent.startswith("scene") or items[row.parent].kind!="menu":
            raise ValueError("invalid scene node")
        if not row.name or not isinstance(row.order,int):
            raise ValueError("invalid scene label")
        if row.members:
            members=tuple(row.members)
            if len(members)>MAX_MENU_QUERIES or len(set(members))!=len(members) or any(cid not in registry.by_id for cid in members):
                raise ValueError("invalid scene members")
            signatures={(menu.capabilities[cid].get("parameter"),menu.capabilities[cid].get("parameter_year_offset",0),tuple(sorted(menu.capabilities[cid].get("parameter_slots",{})))) for cid in members}
            if len(signatures)!=1 or not set(row.supplements)<set(members) or not set(row.stop_on)<=STOP_CONDITIONS or (row.anchor and row.anchor not in set(members)-set(row.supplements)):
                raise ValueError("incompatible scene")
            specs[row.id]=SceneSpec(members,row.anchor,row.supplements,row.stop_on)
        elif row.anchor or row.supplements or row.stop_on:
            raise ValueError("invalid category")
        original=items.get(row.alias_of)
        icon=original.icon if original else ""
        items[row.id]=Item(row.id,menu._label(row.name),row.parent,row.order,"scene" if row.members else "menu",icon=icon)
        if row.alias_of:
            if original is None or original.kind!="menu":
                raise ValueError("invalid scene alias")
            for key,cid in menu.aliases.items():
                if cid==row.alias_of:
                    aliases[key]=row.id
    for node in (root,*(row.id for row in rows)):
        children[node]=tuple(sorted((x for x in items.values() if x.parent==node),key=lambda x:(x.order,x.id)))
    # Keep external and not-yet-projected modules reachable.
    replaced={r.alias_of for r in rows if r.parent==root}
    children[root]=tuple(sorted(children[root]+tuple(x for x in children["root"] if x.id not in replaced),key=lambda x:(x.order,x.id)))
    menu.items,menu.children,menu.scenes,menu.scene_aliases=items,children,specs,aliases
