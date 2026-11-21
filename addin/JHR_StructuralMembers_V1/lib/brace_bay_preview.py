"""Aperçu du contreventement dans la scène Fusion."""

from . import brace_bay, plate_preview


def draw(graphics, plan):
    sections = (brace_bay.branch_section(branch, index) for index, branch in enumerate(plan.branches, 1))
    plate_preview.draw_plates(graphics, sections, fill_rgb=(115, 189, 245), edge_rgb=(51, 135, 206))
    plate_preview.draw_plates(graphics, plan.plates)
