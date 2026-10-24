"""Evidence matrix. Counts independent study families: one paper in three databases is one."""

from dataclasses import dataclass

from bionexus.contracts.evidence import EvidenceRecord, Stance


@dataclass(frozen=True)
class MatrixRow:
    target: str
    supporting_families: int
    opposing_families: int
    unknown_families: int
    evidence_ids: tuple[str, ...]

    @property
    def net_stance(self) -> Stance:
        if self.supporting_families > self.opposing_families:
            return Stance.SUPPORTS
        if self.opposing_families > self.supporting_families:
            return Stance.OPPOSES
        return Stance.UNKNOWN


def _families(records: list[EvidenceRecord], stance: Stance) -> int:
    return len({r.study_family for r in records if r.stance is stance})


def build_matrix(records: list[EvidenceRecord]) -> list[MatrixRow]:
    targets = sorted({record.target for record in records})
    return [_row_for(target, [r for r in records if r.target == target]) for target in targets]


def _row_for(target: str, group: list[EvidenceRecord]) -> MatrixRow:
    return MatrixRow(
        target=target,
        supporting_families=_families(group, Stance.SUPPORTS),
        opposing_families=_families(group, Stance.OPPOSES),
        unknown_families=_families(group, Stance.UNKNOWN),
        evidence_ids=tuple(sorted(r.evidence_id for r in group)),
    )
