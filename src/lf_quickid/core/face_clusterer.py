from __future__ import annotations

import numpy as np
from sklearn.cluster import DBSCAN

from lf_quickid.core.models import FaceGroup, FaceRecord


def cluster_faces(faces: list[FaceRecord], similarity_threshold: float = 0.55) -> list[FaceGroup]:
    if not faces:
        return []

    embeddings = np.vstack([_normalize(face.embedding) for face in faces])
    distance_threshold = 1.0 - similarity_threshold
    labels = DBSCAN(eps=distance_threshold, min_samples=1, metric="cosine").fit_predict(embeddings)

    groups_by_label: dict[int, FaceGroup] = {}
    for label, face in zip(labels, faces, strict=True):
        group = groups_by_label.setdefault(int(label), FaceGroup(label=f"人物 {len(groups_by_label) + 1}"))
        group.faces.append(face)

    return sorted(groups_by_label.values(), key=lambda group: len(group.faces), reverse=True)


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return vector
    return vector / norm
