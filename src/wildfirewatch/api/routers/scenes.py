from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from wildfirewatch.api.schemas import SceneOut
from wildfirewatch.db.models import Scene
from wildfirewatch.db.session import get_session

router = APIRouter(prefix="/scenes", tags=["scenes"])


def _to_out(scene: Scene) -> SceneOut:
    return SceneOut(
        id=scene.id,
        stac_id=scene.stac_id,
        satellite=scene.satellite,
        sensing_time=scene.sensing_time,
        cloud_cover=scene.cloud_cover,
        bbox=mapping(to_shape(scene.bbox)),
        bands=scene.bands,
        processing_status=scene.processing_status,
    )


@router.get("", response_model=list[SceneOut])
def list_scenes(session: Session = Depends(get_session)):
    scenes = session.execute(select(Scene).order_by(Scene.sensing_time.desc())).scalars().all()
    return [_to_out(s) for s in scenes]


@router.get("/{scene_id}", response_model=SceneOut)
def get_scene(scene_id: str, session: Session = Depends(get_session)):
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="scene not found")
    return _to_out(scene)
