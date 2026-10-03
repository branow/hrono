"""A registry collection as a FORM, derived from its own pydantic model (#200).

Settings used to be five textareas of JSON. That is the right surface for the
API and the wrong one for a person: adding a model meant knowing the schema by
heart, every typo came back as a validation error after the fact, and the one
thing an operator wanted to do most — add a second model, drop one — read as
editing a wall of braces.

So each collection is rendered as fields. The fields are not written out here:
they are READ OFF the collection's pydantic model, which is the same model the
API validates against, so a field added to `Model` appears on this page with no
edit to the dashboard at all. Writing them out by hand would be a second schema
that drifts from the first, and the drift would be silent — a field nobody can
set, or one this page offers that the validator refuses.

Two shapes exist in the registry and both are handled here:

- a plain model (`models`, `prompts`, `trees`) — one set of fields
- a discriminated union (`sources`, `connections`) — one set PER variant, with
  the discriminator (``type``, ``provider``) choosing between them

A union is a two-step add: pick the variant, then fill its fields. There is no
JavaScript on this dashboard, so the alternative was rendering every variant at
once and reading back the one the operator meant — five near-identical forms
stacked on a page, four of them wrong.
"""

from __future__ import annotations

import json
import types
import typing
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from pydantic import BaseModel

from hrono.registry.descriptor import Descriptor
from hrono.registry.write import MASK

# Which string fields get a box rather than a line. Judged by name, and kept
# HERE rather than on the descriptor: how tall an input is, is this page's
# business and not the registry's. A value is also promoted to a box when what
# is already stored has newlines in it, so a long config is never editable
# through a one-line input whatever it is called.
ROOMY = frozenset({"template", "url", "key", "token"})
# The prefix every field posts under, so one hidden input cannot collide with
# a config field called `tree` or `variant`.
PREFIX = "f."


@dataclass(frozen=True)
class Field:
    """One input: where it lives in the config, and how to draw it."""

    path: str  # dotted, e.g. "auth.key"
    label: str  # the last segment, e.g. "key"
    group: str  # the containing object, "" at the top level
    kind: str  # text | roomy | secret | choice | lines | toggle | number | json
    required: bool
    value: str
    checked: bool = False
    choices: tuple[str, ...] = ()
    picked: tuple[str, ...] = ()

    @property
    def input_name(self) -> str:
        return f"{PREFIX}{self.path}"


@dataclass(frozen=True)
class Variant:
    """One shape a collection's item may take."""

    name: str  # the discriminator value; "" when the collection has one shape
    fields: tuple[Field, ...] = dataclass_field(default_factory=tuple)


@dataclass(frozen=True)
class Form:
    """Every shape an item may take, and which one these values are."""

    collection: str
    discriminator: str  # "type" / "provider"; "" when there is one shape
    variants: tuple[Variant, ...]
    chosen: str

    @property
    def fields(self) -> tuple[Field, ...]:
        """The chosen variant's fields — what a template actually renders."""
        for variant in self.variants:
            if variant.name == self.chosen:
                return variant.fields
        return self.variants[0].fields if self.variants else ()

    @property
    def picks(self) -> bool:
        """Does adding one of these start by choosing a variant?"""
        return bool(self.discriminator) and len(self.variants) > 1


def form_for(
    descriptor: Descriptor,
    config: Mapping[str, object] | None = None,
    variant: str = "",
    options: Mapping[str, Sequence[str]] | None = None,
) -> Form:
    """The form for one item of ``descriptor``'s collection.

    ``config`` fills it (an edit); omit it for a blank one (an add). ``variant``
    picks the shape when the collection is a union and there is no config to
    read it off. ``options`` names what a field may REFER to — the registered
    sources a tree maps, the registered connections a model calls — turning a
    free-text field into a pick. The model cannot know those: they are rows in
    another collection, and the only thing that stops a typo today is the
    validation hook's refusal AFTER the save, which is the worse way to learn
    a name.
    """
    values = dict(config or {})
    discriminator, shapes = _shapes(descriptor.model)
    chosen = str(values.get(discriminator, "")) if discriminator else ""
    chosen = chosen or variant or (shapes[0][0] if shapes else "")
    secrets = {".".join(path) for path in descriptor.secret_paths}
    return Form(
        collection=descriptor.collection,
        discriminator=discriminator,
        variants=tuple(
            Variant(
                name=name,
                fields=tuple(
                    _fields(
                        model,
                        values if name == chosen else {},
                        secrets,
                        dict(options or {}),
                        skip=discriminator,
                    )
                ),
            )
            for name, model in shapes
        ),
        chosen=chosen,
    )


def config_from(
    descriptor: Descriptor,
    posted: Mapping[str, Sequence[str]],
    options: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    """Rebuild a config from what a form posted.

    Only the CHOSEN variant's fields are read. A blank optional field is left
    out rather than written as an empty string, so the model's own default is
    what lands in the database — an absent `role` and a `role` of `""` are not
    the same config, and only one of them validates.
    """
    discriminator, shapes = _shapes(descriptor.model)
    chosen = _first(posted, PREFIX + discriminator) if discriminator else ""
    chosen = chosen or _first(posted, "variant")
    model = _pick(shapes, chosen)
    built: dict[str, object] = {}
    if discriminator and chosen:
        built[discriminator] = chosen
    secrets = {".".join(path) for path in descriptor.secret_paths}
    for field in _fields(
        model, {}, secrets, dict(options or {}), skip=discriminator
    ):
        value = _read(field, posted)
        if value is not None:
            _put(built, field.path, value)
    return built


def _shapes(
    model: type[BaseModel],
) -> tuple[str, tuple[tuple[str, type[BaseModel]], ...]]:
    """A model's variants: its discriminator and one shape per union member.

    A plain model is one unnamed shape, so everything downstream reads the same
    whether the collection is a union or not.
    """
    root = model.model_fields.get("root")
    if root is None or not root.discriminator:
        return "", (("", model),)
    members = typing.get_args(root.annotation)
    return str(root.discriminator), tuple(
        (_tag(member, str(root.discriminator)), member) for member in members
    )


def _tag(model: type[BaseModel], discriminator: str) -> str:
    """The literal value that selects this union member."""
    annotation = model.model_fields[discriminator].annotation
    values = typing.get_args(annotation)
    return str(values[0]) if values else ""


def _pick(
    shapes: tuple[tuple[str, type[BaseModel]], ...], chosen: str
) -> type[BaseModel]:
    for name, model in shapes:
        if name == chosen:
            return model
    return shapes[0][1]


def _fields(
    model: type[BaseModel],
    values: Mapping[str, object],
    secrets: set[str],
    options: Mapping[str, Sequence[str]],
    skip: str = "",
    prefix: str = "",
) -> list[Field]:
    """Every input one model needs, nested objects flattened to dotted paths.

    ``skip`` drops the discriminator: it is chosen once, for the whole item,
    and an editable copy of it inside the fields would be a second answer to
    the same question.
    """
    out: list[Field] = []
    for name, info in model.model_fields.items():
        if not prefix and name == skip:
            continue
        path = f"{prefix}{name}"
        inner, optional = _unwrap(info.annotation)
        held = _at(values, path)
        if _is_model(inner):
            out.extend(
                _fields(inner, values, secrets, options, prefix=f"{path}.")
            )
            continue
        out.append(
            _field(
                path=path,
                label=name,
                group=prefix.rstrip("."),
                annotation=inner,
                required=info.is_required() and not optional,
                held=held,
                secret=path in secrets,
                offered=tuple(options.get(path, ())),
            )
        )
    return out


def _field(
    path: str,
    label: str,
    group: str,
    annotation: object,
    required: bool,
    held: object,
    secret: bool,
    offered: tuple[str, ...],
) -> Field:
    choices = (
        tuple(str(value) for value in typing.get_args(annotation))
        if typing.get_origin(annotation) is typing.Literal
        else ()
    )
    kind = _kind(annotation, label, held, secret, bool(choices))
    # a field that REFERS to another collection is a pick over what is
    # registered, whatever the model's own type says it is
    if offered:
        kind = "multi" if kind == "lines" else "choice"
        choices = offered
    return Field(
        path=path,
        label=label,
        group=group,
        kind=kind,
        required=required,
        value=_shown(kind, held),
        checked=bool(held),
        choices=choices,
        picked=_picked(kind, held),
    )


def _picked(kind: str, held: object) -> tuple[str, ...]:
    """Which of a multi-pick's options this config already names."""
    if kind != "multi" or not isinstance(held, (list, tuple)):
        return ()
    return tuple(str(item) for item in held)


def _kind(
    annotation: object, label: str, held: object, secret: bool, choice: bool
) -> str:
    if secret:
        return "secret"
    if choice:
        return "choice"
    if annotation is bool:
        return "toggle"
    if annotation in (int, float):
        return "number"
    if _is_list_of_str(annotation):
        return "lines"
    if annotation is str:
        if label in ROOMY or (isinstance(held, str) and "\n" in held):
            return "roomy"
        return "text"
    return "json"


def _shown(kind: str, held: object) -> str:
    """One stored value as the text an input carries."""
    if held is None:
        return ""
    if kind in ("lines", "multi"):
        return "\n".join(str(item) for item in held)  # type: ignore[union-attr]
    if kind == "toggle":
        return ""
    if kind in ("text", "roomy", "secret", "choice", "number"):
        return str(held)
    return json.dumps(held, indent=2)


def _read(field: Field, posted: Mapping[str, Sequence[str]]) -> object | None:
    """One field's posted value as the config wants it, or None to omit it."""
    if field.kind == "toggle":
        return bool(_first(posted, field.input_name))
    if field.kind == "multi":
        picked = [str(v).strip() for v in posted.get(field.input_name, ())]
        chosen = [value for value in picked if value]
        return chosen if chosen or field.required else None
    raw = _first(posted, field.input_name).strip()
    if not raw:
        # A blank field is an ABSENT one, required or not. Sending `""` through
        # for a required field looked like the way to get the error attributed
        # to that field — but `url: str` accepts an empty string, so a source
        # with no url validated, saved, and failed later at the reach check
        # with a message about git rather than about the empty box (#200).
        # Omitted, pydantic says "Field required" against the field itself.
        return None
    if field.kind == "secret" and raw == MASK:
        return MASK  # `unmask` turns it back into the credential already held
    if field.kind == "lines":
        return [line.strip() for line in raw.splitlines() if line.strip()]
    if field.kind == "number":
        return _number(raw)
    if field.kind == "json":
        return json.loads(raw)
    return raw


def _number(raw: str) -> object:
    try:
        return int(raw)
    except ValueError:
        return float(raw)


def _unwrap(annotation: object) -> tuple[object, bool]:
    """Strip ``| None``: the inner type, and whether None was allowed."""
    if typing.get_origin(annotation) not in (typing.Union, types.UnionType):
        return annotation, False
    members = [
        arg for arg in typing.get_args(annotation) if arg is not type(None)
    ]
    optional = len(members) != len(typing.get_args(annotation))
    if len(members) != 1:
        return annotation, optional
    return members[0], optional


def _is_model(annotation: object) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _is_list_of_str(annotation: object) -> bool:
    if typing.get_origin(annotation) is not list:
        return False
    args = typing.get_args(annotation)
    return bool(args) and args[0] is str


def _at(values: Mapping[str, object], path: str) -> object:
    """Follow a dotted path into a stored config, or None where it stops."""
    here: object = values
    for part in path.split("."):
        if not isinstance(here, Mapping) or part not in here:
            return None
        here = here[part]
    return here


def _put(config: dict[str, object], path: str, value: object) -> None:
    """Set a dotted path, making the objects along the way."""
    parts = path.split(".")
    here = config
    for part in parts[:-1]:
        nested = here.setdefault(part, {})
        if not isinstance(nested, dict):
            return
        here = nested
    here[parts[-1]] = value


def _first(posted: Mapping[str, Sequence[str]], key: str) -> str:
    values = posted.get(key, ())
    return str(values[0]) if values else ""
