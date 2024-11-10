# Copyright Kevin Deldycke <kevin@deldycke.com> and contributors.
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""Group models collection of platforms. Also referred as families or categories."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable, Iterator, Union

from boltons.iterutils import flatten_iter

from .platform import Platform

_TPlatformSources = Union[Platform, "Group"]
_TNestedSources = Iterable[Union[_TPlatformSources, Iterable["_TNestedSources"]]]
"""Types for arbitrary nested sources of ``Platforms``."""


@dataclass(frozen=True)
class Group:
    """A ``Group`` identify a collection of ``Platform``.

    Used to group platforms of the same family.

    `set()`-like methods are available and performed on the platform objects the group
    contain (in the ``self.platforms`` data field).
    """

    id: str
    """Unique ID of the group."""

    name: str
    """User-friendly description of a group."""

    icon: str = field(repr=False, default="❓")
    """Icon of the group."""

    platforms: tuple[Platform, ...] = field(repr=False, default_factory=tuple)
    """Sorted list of platforms that belong to this group."""

    platform_ids: frozenset[str] = field(default_factory=frozenset)
    """Set of platform IDs that belong to this group.

    Used to test platform overlaps between groups.
    """

    def __post_init__(self):
        """Deduplicate platforms and sort them by IDs."""
        object.__setattr__(
            self,
            "platforms",
            tuple(sorted(set(self.platforms), key=lambda p: p.id)),
        )
        # Double check there are no Platform objects sharing the same IDs.
        id_counter = Counter(p.id for p in self.platforms)
        if len(set(id_counter)) != len(self.platforms):
            duplicates = (k for k, v in dict(id_counter).items() if v > 1)
            raise ValueError(
                "The group is not allowed to have platforms with duplicate IDs: "
                f"{', '.join(duplicates)}"
            )
        object.__setattr__(self, "platform_ids", frozenset(id_counter))

    def __iter__(self) -> Iterator[Platform]:
        """Iterate over the platforms of the group."""
        yield from self.platforms

    def __len__(self) -> int:
        """Return the number of platforms in the group."""
        return len(self.platforms)

    def __contains__(self, platform: Platform) -> bool:
        """Test ``platform`` for membership in the group."""
        return platform in self.platforms

    @staticmethod
    def _extract_platforms(other: _TNestedSources) -> Iterator[Platform]:
        """Returns all platforms found in ``other``."""
        if isinstance(other, Platform):
            yield other
        elif isinstance(other, Group):
            yield from other.platforms
        elif isinstance(other, Iterable):
            for item in flatten_iter(other):
                yield from Group._extract_platforms(item)
        else:
            raise ValueError

    @staticmethod
    def _extract_platform_ids(other: _TNestedSources) -> frozenset[str]:
        """Returns all platform IDs found in ``other``."""
        return frozenset(p.id for p in Group._extract_platforms(other))

    def isdisjoint(self, other: _TNestedSources) -> bool:
        """Return `True` if the group has no platforms in common with ``other``.

        Groups are disjoint if and only if their intersection is an empty set.

        ``other`` can be an arbitrarily nested ``Iterable`` of ``Group`` and ``Platform``.
        """
        return set(self.platforms).isdisjoint(self._extract_platforms(other))

    def fullyintersects(self, other: _TNestedSources) -> bool:
        """Return `True` if the group has all platforms in common with ``other``."""
        return set(self.platforms) == set(self._extract_platforms(other))

    def issubset(self, other: _TNestedSources) -> bool:
        """Test whether every platforms in the group is in other."""
        return set(self.platforms).issubset(self._extract_platforms(other))

    __le__ = issubset

    def __lt__(self, other: _TNestedSources) -> bool:
        """Test whether every platform in the group is in other, but not all."""
        return self <= other and set(self.platforms) != set(
            self._extract_platforms(other)
        )

    def issuperset(self, other: _TNestedSources) -> bool:
        """Test whether every platform in other is in the group."""
        return set(self.platforms).issuperset(self._extract_platforms(other))

    __ge__ = issuperset

    def __gt__(self, other: _TNestedSources) -> bool:
        """Test whether every platform in other is in the group, but not all."""
        return self >= other and set(self.platforms) != set(
            self._extract_platforms(other)
        )

    def union(self, *others: _TNestedSources) -> Group:
        """Return a new ``Group`` with platforms from the group and all others.

        ..caution::
            The new ``Group`` will inherits the metadata of the first one. All other
            groups' metadata will be ignored.
        """
        return Group(
            self.id,
            self.name,
            self.icon,
            set(self.platforms).union(
                *(self._extract_platforms(other) for other in others)
            ),
        )

    __or__ = union

    def intersection(self, *others: _TNestedSources) -> Group:
        """Return a new ``Group`` with platforms common to the group and all others.

        ..caution::
            The new ``Group`` will inherits the metadata of the first one. All other
            groups' metadata will be ignored.
        """
        return Group(
            self.id,
            self.name,
            self.icon,
            set(self.platforms).intersection(
                *(self._extract_platforms(other) for other in others)
            ),
        )

    __and__ = intersection

    def difference(self, *others: _TNestedSources) -> Group:
        """Return a new ``Group`` with platforms in the group that are not in the others.

        ..caution::
            The new ``Group`` will inherits the metadata of the first one. All other
            groups' metadata will be ignored.
        """
        return Group(
            self.id,
            self.name,
            self.icon,
            set(self.platforms).difference(
                *(self._extract_platforms(other) for other in others)
            ),
        )

    __sub__ = difference

    def symmetric_difference(self, other: _TNestedSources) -> Group:
        """Return a new ``Group`` with platforms in either the group or other but not both.

        ..caution::
            The new ``Group`` will inherits the metadata of the first one. All other
            groups' metadata will be ignored.
        """
        return Group(
            self.id,
            self.name,
            self.icon,
            set(self.platforms).symmetric_difference(self._extract_platforms(other)),
        )

    __xor__ = symmetric_difference


def reduce(items: Iterable[Group | Platform]) -> set[Group | Platform]:
    """Reduce a collection of ``Group`` and ``Platform`` to a minimal set.

    Returns a deduplicated set of ``Group`` and ``Platform`` that covers the same exact
    platforms as the original input, but group as much platforms as possible, to reduce
    the number of items.

    .. hint::
        Maybe this could be solved with some `Euler diagram
        <https://en.wikipedia.org/wiki/Euler_diagram>`_ algorithms, like those
        implemented in `eule <https://github.com/trouchet/eule>`_.

        This is being discussed upstream at `trouchet/eule#120
        <https://github.com/trouchet/eule/issues/120>`_.

    .. todo::
        Should we rename or alias this method to `collapse()`? Cannot decide if it is
        more descriptive or not...
    """
    # Prevent circular imports.
    from .group_data import ALL_GROUPS

    # Collect all platforms.
    platforms: set[Platform] = set()
    for item in items:
        if isinstance(item, Group):
            platforms.update(item.platforms)
        else:
            platforms.add(item)

    # List any group matching the platforms.
    valid_groups: set[Group] = set()
    for group in ALL_GROUPS:
        if group.issubset(platforms):
            valid_groups.add(group)

    # Test all combination of groups to find the smallest set of groups + platforms.
    min_items: int = 0
    results: list[set[Group | Platform]] = []
    # Serialize group sets for deterministic lookups. Sort them by platform count.
    groups = tuple(sorted(valid_groups, key=len, reverse=True))
    for subset_size in range(1, len(groups) + 1):
        # If we already have a solution that involves less items than the current
        # subset of groups we're going to evaluates, there is no point in continuing.
        if min_items and subset_size > min_items:
            break

        for group_subset in combinations(groups, subset_size):
            # If any group overlaps another, there is no point in exploring this subset.
            if not all(g[0].isdisjoint(g[1]) for g in combinations(group_subset, 2)):
                continue

            # Remove all platforms covered by the groups.
            ungrouped_platforms = platforms.copy()
            for group in group_subset:
                ungrouped_platforms.difference_update(group.platforms)

            # Merge the groups and the remaining platforms.
            reduction = ungrouped_platforms.union(group_subset)
            reduction_size = len(reduction)

            # Reset the results if we have a new solution that is better than the
            # previous ones.
            if not results or reduction_size < min_items:
                results = [reduction]
                min_items = reduction_size
            # If the solution is as good as the previous one, add it to the results.
            elif reduction_size == min_items:
                results.append(reduction)

    if len(results) > 1:
        msg = f"Multiple solutions found: {results}"
        raise RuntimeError(msg)

    # If no reduced solution was found, return the original platforms.
    if not results:
        return platforms  # type: ignore[return-value]

    return results.pop()