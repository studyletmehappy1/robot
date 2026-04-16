import logging

logger = logging.getLogger(__name__)


def stop_for_action():
    logger.info("motion backend placeholder: stop_for_action() is not connected yet")
    return False


def resume_motion():
    logger.info("motion backend placeholder: resume_motion() is not connected yet")
    return False


def move(vx, vy, wz):
    logger.info(
        "motion backend placeholder: move(vx=%s, vy=%s, wz=%s) is not connected yet",
        vx,
        vy,
        wz,
    )
    return False
