import cv2
import numpy as np
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(SCRIPT_DIR, "debug")
JPEG_DIR = os.path.join(SCRIPT_DIR, "jpegs")

if not os.path.exists(DEBUG_DIR):
    os.makedirs(DEBUG_DIR)

CARD_WIDTH = 734
CARD_HEIGHT = 1024


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def get_intersection(line1, line2):
    vx1, vy1, x1, y1 = line1
    vx2, vy2, x2, y2 = line2
    cross = vx1 * vy2 - vy1 * vx2
    if abs(cross) < 1e-6:
        return None
    dx = x2 - x1
    dy = y2 - y1
    t1 = (dx * vy2 - dy * vx2) / cross
    return [float(x1 + vx1 * t1), float(y1 + vy1 * t1)]


def get_true_corners(contour, image_shape):
    x, y, w, h = cv2.boundingRect(contour)
    cx, cy = x + w/2, y + h/2
    left_pts, right_pts, top_pts, bottom_pts = [], [], [], []
    x_margin = w * 0.15
    y_margin = h * 0.15

    for pt in contour:
        px, py = pt[0]
        if x + x_margin < px < x + w - x_margin:
            if py < cy:
                top_pts.append(pt[0])
            else:
                bottom_pts.append(pt[0])
        if y + y_margin < py < y + h - y_margin:
            if px < cx:
                left_pts.append(pt[0])
            else:
                right_pts.append(pt[0])

    try:
        top_line = cv2.fitLine(
            np.array(top_pts), cv2.DIST_L2, 0, 0.01, 0.01).flatten()
        bottom_line = cv2.fitLine(
            np.array(bottom_pts), cv2.DIST_L2, 0, 0.01, 0.01).flatten()
        left_line = cv2.fitLine(
            np.array(left_pts), cv2.DIST_L2, 0, 0.01, 0.01).flatten()
        right_line = cv2.fitLine(
            np.array(right_pts), cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    except Exception:
        return None

    tl = get_intersection(top_line, left_line)
    tr = get_intersection(top_line, right_line)
    bl = get_intersection(bottom_line, left_line)
    br = get_intersection(bottom_line, right_line)

    if any(pt is None for pt in [tl, tr, bl, br]):
        return None
    return np.array([tl, tr, br, bl], dtype="float32")


def isolate_card(image_path, prefix="front"):
    image = cv2.imread(image_path)
    if image is None:
        return None

    if "front" in prefix:
        b, g, r = cv2.split(image)
        yellow_isolated = cv2.subtract(r, b)
        blurred = cv2.GaussianBlur(yellow_isolated, (15, 15), 0)
        _, thresh = cv2.threshold(blurred, 30, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cv2.rectangle(closed, (0, 0), (closed.shape[1], closed.shape[0]), 0, 5)
    else:
        b, g, r = cv2.split(image)
        blue_isolated = cv2.subtract(b, r)
        blurred_blue = cv2.GaussianBlur(blue_isolated, (15, 15), 0)
        _, blue_thresh = cv2.threshold(
            blurred_blue, 20, 255, cv2.THRESH_BINARY)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred_gray = cv2.bilateralFilter(gray, 11, 50, 50)
        _, white_thresh = cv2.threshold(
            blurred_gray, 160, 255, cv2.THRESH_BINARY)
        combined_thresh = cv2.bitwise_or(blue_thresh, white_thresh)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed = cv2.morphologyEx(combined_thresh, cv2.MORPH_CLOSE, kernel)
        cv2.rectangle(closed, (0, 0), (closed.shape[1], closed.shape[0]), 0, 5)

    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest_contour = max(contours, key=cv2.contourArea)

    solid_mask = np.zeros_like(closed)
    cv2.drawContours(solid_mask, [largest_contour], -1, 255, -1)

    pts = get_true_corners(largest_contour, image.shape)

    if pts is None:
        rect = cv2.minAreaRect(largest_contour)
        box = cv2.boxPoints(rect)
        pts = np.int32(box)

    rect_ordered = order_points(pts.astype("float32"))
    dst = np.array([
        [0, 0],
        [CARD_WIDTH - 1, 0],
        [CARD_WIDTH - 1, CARD_HEIGHT - 1],
        [0, CARD_HEIGHT - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect_ordered, dst)
    warped = cv2.warpPerspective(image, M, (CARD_WIDTH, CARD_HEIGHT))
    warped_mask = cv2.warpPerspective(solid_mask, M, (CARD_WIDTH, CARD_HEIGHT))

    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_05_warped_final.jpg"), warped)
    print(f"  -> Isolated & warped {prefix}.")

    return warped, warped_mask


def localize_borders(warped_img, prefix="front"):
    img_h, img_w = warped_img.shape[:2]
    PCT_LR, PCT_TB = 0.10, 0.10

    left_bound = int(img_w * PCT_LR)
    right_bound = int(img_w * (1 - PCT_LR))
    top_bound = int(img_h * PCT_TB)
    bottom_bound = int(img_h * (1 - PCT_TB))

    y_margin = int(img_h * 0.20)
    x_margin = int(img_w * 0.20)

    regions = {
        "left_strip": warped_img[y_margin: img_h - y_margin, 0: left_bound],
        "right_strip": warped_img[y_margin: img_h - y_margin, right_bound: img_w],
        "top_strip": warped_img[0: top_bound, x_margin: img_w - x_margin],
        "bottom_strip": warped_img[bottom_bound: img_h, x_margin: img_w - x_margin]
    }
    return regions


def find_border_width(strip_img, prefix="front", is_vertical=False, reverse=False):
    blurred_strip = cv2.GaussianBlur(strip_img, (3, 3), 0)
    percentile_val = 80 if "front" in prefix else 50

    if is_vertical:
        profile_bgr = np.percentile(
            blurred_strip, percentile_val, axis=1).astype(np.float32)
    else:
        profile_bgr = np.percentile(
            blurred_strip, percentile_val, axis=0).astype(np.float32)

    if reverse:
        profile_bgr = profile_bgr[::-1]

    safe_zone = profile_bgr[20:30]
    true_bgr = np.median(safe_zone, axis=0)
    true_hsv = cv2.cvtColor(np.uint8([[true_bgr]]), cv2.COLOR_BGR2HSV)[0][0]
    true_h, true_s, true_v = int(true_hsv[0]), int(
        true_hsv[1]), int(true_hsv[2])

    base_noise = np.std(safe_zone, axis=0).sum()
    trigger_threshold = max(30.0, base_noise * 3.0)

    locked_on_border = False
    rolling_buffer = []

    for i in range(5, len(profile_bgr)):
        curr_bgr = profile_bgr[i]
        curr_hsv = cv2.cvtColor(
            np.uint8([[curr_bgr]]), cv2.COLOR_BGR2HSV)[0][0]
        curr_h, curr_s, curr_v = int(curr_hsv[0]), int(
            curr_hsv[1]), int(curr_hsv[2])

        if not locked_on_border:
            hue_diff = abs(curr_h - true_h)
            if hue_diff > 90:
                hue_diff = 180 - hue_diff
            color_diff = np.sqrt(((hue_diff) * 2)**2 + (curr_s - true_s)**2)

            if color_diff < 30:
                locked_on_border = True
                rolling_buffer = [curr_bgr] * 5
        else:
            base_bgr = np.median(rolling_buffer, axis=0).astype(np.uint8)
            base_hsv = cv2.cvtColor(
                np.uint8([[base_bgr]]), cv2.COLOR_BGR2HSV)[0][0]
            base_h, base_s, base_v = int(base_hsv[0]), int(
                base_hsv[1]), int(base_hsv[2])

            hue_diff_roll = abs(curr_h - base_h)
            if hue_diff_roll > 90:
                hue_diff_roll = 180 - hue_diff_roll

            rolling_diff = np.sqrt(
                ((hue_diff_roll) * 2)**2 + (curr_s - base_s)**2 + ((curr_v - base_v) * 0.5)**2)

            hue_diff_anchor = abs(curr_h - true_h)
            if hue_diff_anchor > 90:
                hue_diff_anchor = 180 - hue_diff_anchor

            anchor_diff = np.sqrt(
                ((hue_diff_anchor) * 2)**2 + (curr_s - true_s)**2 + ((curr_v - true_v) * 0.5)**2)

            if rolling_diff > trigger_threshold or anchor_diff > (trigger_threshold * 1.5):
                return i
            else:
                rolling_buffer.append(curr_bgr)
                if len(rolling_buffer) > 10:
                    rolling_buffer.pop(0)

    return 15


def segment_edges(warped_img, prefix="front"):
    print(f"\n--- Phase 5: Edge Segmentation ({prefix.upper()}) ---")
    img_h, img_w = warped_img.shape[:2]
    EDGE_MARGIN, SAFE_PAD = 23, 2

    edges = {
        "top": warped_img[SAFE_PAD:EDGE_MARGIN, EDGE_MARGIN: img_w - EDGE_MARGIN].copy(),
        "bottom": warped_img[img_h - EDGE_MARGIN: img_h - SAFE_PAD, EDGE_MARGIN: img_w - EDGE_MARGIN].copy(),
        "left": warped_img[EDGE_MARGIN: img_h - EDGE_MARGIN, SAFE_PAD:EDGE_MARGIN].copy(),
        "right": warped_img[EDGE_MARGIN: img_h - EDGE_MARGIN, img_w - EDGE_MARGIN: img_w - SAFE_PAD].copy()
    }

    # Debug Frame
    debug_img = warped_img.copy()
    cv2.rectangle(debug_img, (EDGE_MARGIN, EDGE_MARGIN),
                  (img_w - EDGE_MARGIN, img_h - EDGE_MARGIN), (0, 0, 0), -1)
    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_08_edge_segmentation.jpg"), debug_img)
    print("  -> Extracted damage zones. Visual frame saved.")

    return edges


def analyze_centering(regions, warped_img, prefix="front"):
    print(f"\n--- Phase 4: Centering Analysis ({prefix.upper()}) ---")
    left_w = find_border_width(
        regions["left_strip"], prefix, is_vertical=False, reverse=False)
    right_w = find_border_width(
        regions["right_strip"], prefix, is_vertical=False, reverse=True)
    top_w = find_border_width(
        regions["top_strip"], prefix, is_vertical=True, reverse=False)
    bottom_w = find_border_width(
        regions["bottom_strip"], prefix, is_vertical=True, reverse=True)

    print(f"  Measured Left: {left_w}px | Right: {right_w}px")
    print(f"  Measured Top:  {top_w}px | Bottom: {bottom_w}px")

    lr_total, tb_total = left_w + right_w, top_w + bottom_w
    lr_worst = max(left_w, right_w)
    tb_worst = max(top_w, bottom_w)

    lr_ratio = (lr_worst / lr_total) * 100
    tb_ratio = (tb_worst / tb_total) * 100
    worst_overall = max(lr_ratio, tb_ratio)

    grade = 6
    if worst_overall <= 53.0:
        grade = 10
    elif worst_overall <= 56.5:
        grade = 9
    elif worst_overall <= 60.0:
        grade = 8
    elif worst_overall <= 65.0:
        grade = 7
    elif worst_overall <= 75.0:
        grade = 6
    else:
        grade = 5

    print(f"  ---> Estimated PSA Centering Grade: {grade}")

    debug_img = warped_img.copy()
    img_h, img_w = debug_img.shape[:2]
    cv2.rectangle(debug_img, (left_w, top_w),
                  (img_w - right_w, img_h - bottom_w), (0, 255, 0), 2)
    cx, cy = img_w // 2, img_h // 2
    cv2.line(debug_img, (cx, 0), (cx, img_h), (255, 0, 0), 1)
    cv2.line(debug_img, (0, cy), (img_w, cy), (255, 0, 0), 1)
    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_07_laser_measurements.jpg"), debug_img)
    print("  -> Visual measurements saved.")

    return {"grade": grade, "worst_ratio": worst_overall}


def extract_damage_masks(edges, warped_img, prefix="front"):
    masks = {}
    debug_img = warped_img.copy()
    EDGE_MARGIN, SAFE_PAD = 23, 2
    img_h, img_w = warped_img.shape[:2]

    for edge_name, strip in edges.items():
        strip_copy = strip.copy()
        blurred = cv2.GaussianBlur(strip_copy, (3, 3), 0)
        strip_h, strip_w = blurred.shape[:2]

        if edge_name == "top":
            safe_bgr = blurred[-5:, :]
            base_bgr = np.tile(np.median(safe_bgr, axis=0), (strip_h, 1, 1))
        elif edge_name == "bottom":
            safe_bgr = blurred[0:5, :]
            base_bgr = np.tile(np.median(safe_bgr, axis=0), (strip_h, 1, 1))
        elif edge_name == "left":
            safe_bgr = blurred[:, -5:]
            base_bgr = np.tile(np.median(safe_bgr, axis=1)[
                               :, np.newaxis, :], (1, strip_w, 1))
        elif edge_name == "right":
            safe_bgr = blurred[:, 0:5]
            base_bgr = np.tile(np.median(safe_bgr, axis=1)[
                               :, np.newaxis, :], (1, strip_w, 1))

        diff = blurred.astype(np.float32) - base_bgr.astype(np.float32)
        dist = np.linalg.norm(diff, axis=2)

        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        base_gray = cv2.cvtColor(base_bgr.astype(np.uint8), cv2.COLOR_BGR2GRAY)

        if "front" in prefix:
            damage_mask = (dist > 45) & (gray > 130)
        else:
            damage_mask = (dist > 50) & (gray > base_gray + 10)

        mask_8bit = np.where(damage_mask, 255, 0).astype(np.uint8)
        masks[edge_name] = mask_8bit

        # Debugger: Paint RAW hits in yellow
        yellow_strip = np.zeros_like(strip_copy)
        yellow_strip[:] = (0, 255, 255)
        np.copyto(strip_copy, yellow_strip,
                  where=mask_8bit.astype(bool)[:, :, None])

        if edge_name == "top":
            debug_img[SAFE_PAD:EDGE_MARGIN,
                      EDGE_MARGIN: img_w - EDGE_MARGIN] = strip_copy
        elif edge_name == "bottom":
            debug_img[img_h - EDGE_MARGIN: img_h - SAFE_PAD,
                      EDGE_MARGIN: img_w - EDGE_MARGIN] = strip_copy
        elif edge_name == "left":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN,
                      SAFE_PAD:EDGE_MARGIN] = strip_copy
        elif edge_name == "right":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN, img_w -
                      EDGE_MARGIN: img_w - SAFE_PAD] = strip_copy

    cv2.rectangle(debug_img, (EDGE_MARGIN, EDGE_MARGIN),
                  (img_w - EDGE_MARGIN, img_h - EDGE_MARGIN), (0, 0, 0), -1)
    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_09a_RAW_whitening.jpg"), debug_img)
    return masks


def filter_true_damage(masks_0, masks_180):
    print("  -> Cross-referencing 0-deg and 180-deg scans to eliminate glare...")
    true_masks = {}
    true_masks["top"] = cv2.bitwise_and(
        masks_0["top"], cv2.flip(masks_180["bottom"], -1))
    true_masks["bottom"] = cv2.bitwise_and(
        masks_0["bottom"], cv2.flip(masks_180["top"], -1))
    true_masks["left"] = cv2.bitwise_and(
        masks_0["left"], cv2.flip(masks_180["right"], -1))
    true_masks["right"] = cv2.bitwise_and(
        masks_0["right"], cv2.flip(masks_180["left"], -1))
    return true_masks


def evaluate_and_visualize_damage(true_masks, edges_0, warped_img_0, prefix="front"):
    print(
        f"\n--- Phase 6: True Edge Whitening Analysis ({prefix.upper()}) ---")
    damage_stats = {}
    debug_img = warped_img_0.copy()
    EDGE_MARGIN, SAFE_PAD = 23, 2
    img_h, img_w = warped_img_0.shape[:2]

    total_damage_px = 0
    total_edge_px = 0

    for edge_name, mask in true_masks.items():
        strip = edges_0[edge_name].copy()
        damage_px = cv2.countNonZero(mask)
        total_px = strip.shape[0] * strip.shape[1]

        damage_stats[edge_name] = {
            "damage_px": damage_px, "total_px": total_px, "percent": (damage_px / total_px) * 100}

        total_damage_px += damage_px
        total_edge_px += total_px

        # Paint True hits in red
        red_strip = np.zeros_like(strip)
        red_strip[:] = (0, 0, 255)
        np.copyto(strip, red_strip, where=mask.astype(bool)[:, :, None])

        if edge_name == "top":
            debug_img[SAFE_PAD:EDGE_MARGIN,
                      EDGE_MARGIN: img_w - EDGE_MARGIN] = strip
        elif edge_name == "bottom":
            debug_img[img_h - EDGE_MARGIN: img_h - SAFE_PAD,
                      EDGE_MARGIN: img_w - EDGE_MARGIN] = strip
        elif edge_name == "left":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN,
                      SAFE_PAD:EDGE_MARGIN] = strip
        elif edge_name == "right":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN,
                      img_w - EDGE_MARGIN: img_w - SAFE_PAD] = strip

    cv2.rectangle(debug_img, (EDGE_MARGIN, EDGE_MARGIN),
                  (img_w - EDGE_MARGIN, img_h - EDGE_MARGIN), (0, 0, 0), -1)
    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_09_true_whitening_damage.jpg"), debug_img)

    overall_pct = (total_damage_px / total_edge_px) * \
        100 if total_edge_px > 0 else 0
    print(
        f"  Overall True Edge Whitening: {overall_pct:.2f}% ({total_damage_px} pixels)")
    for k, val in damage_stats.items():
        print(f"    -> {k.capitalize()}: {val['percent']:.2f}%")

    print("  -> True damage visualization saved.")
    return damage_stats


def analyze_corners(warped_img, warped_mask, prefix="front"):
    print(f"\n--- Phase 7: Corner Analysis ({prefix.upper()}) ---")
    CORNER_SIZE = 40
    img_h, img_w = warped_img.shape[:2]

    corners = {
        "top_left": warped_img[0:CORNER_SIZE, 0:CORNER_SIZE].copy(),
        "top_right": warped_img[0:CORNER_SIZE, img_w-CORNER_SIZE:img_w].copy(),
        "bottom_left": warped_img[img_h-CORNER_SIZE:img_h, 0:CORNER_SIZE].copy(),
        "bottom_right": warped_img[img_h-CORNER_SIZE:img_h, img_w-CORNER_SIZE:img_w].copy()
    }

    corner_masks = {
        "top_left": warped_mask[0:CORNER_SIZE, 0:CORNER_SIZE],
        "top_right": warped_mask[0:CORNER_SIZE, img_w-CORNER_SIZE:img_w],
        "bottom_left": warped_mask[img_h-CORNER_SIZE:img_h, 0:CORNER_SIZE],
        "bottom_right": warped_mask[img_h-CORNER_SIZE:img_h, img_w-CORNER_SIZE:img_w]
    }

    stats = {}
    debug_canvas = np.zeros_like(warped_img)

    for name, corner in corners.items():
        corner_copy = corner.copy()
        silhouette = corner_masks[name]
        black_mask = (silhouette == 0)

        hsv = cv2.cvtColor(corner_copy, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        gray = cv2.cvtColor(corner_copy, cv2.COLOR_BGR2GRAY)

        if "front" in prefix:
            white_mask = (s < 50) & (v > 150) & (gray > 130)
        else:
            white_mask = (s < 50) & (v > 150)

        white_mask = white_mask & (silhouette == 255)
        white_mask_8bit = np.where(white_mask, 255, 0).astype(np.uint8)
        black_mask_8bit = np.where(black_mask, 255, 0).astype(np.uint8)

        # Paint Debugger
        blue_overlay = np.zeros_like(corner_copy)
        blue_overlay[:] = (255, 0, 0)
        np.copyto(corner_copy, blue_overlay, where=black_mask[:, :, None])

        red_overlay = np.zeros_like(corner_copy)
        red_overlay[:] = (0, 0, 255)
        np.copyto(corner_copy, red_overlay, where=white_mask[:, :, None])

        if name == "top_left":
            debug_canvas[0:CORNER_SIZE, 0:CORNER_SIZE] = corner_copy
        elif name == "top_right":
            debug_canvas[0:CORNER_SIZE, img_w-CORNER_SIZE:img_w] = corner_copy
        elif name == "bottom_left":
            debug_canvas[img_h-CORNER_SIZE:img_h, 0:CORNER_SIZE] = corner_copy
        elif name == "bottom_right":
            debug_canvas[img_h-CORNER_SIZE:img_h,
                         img_w-CORNER_SIZE:img_w] = corner_copy

        stats[name] = {"missing_paper_area": cv2.countNonZero(
            black_mask_8bit), "whitening_px": cv2.countNonZero(white_mask_8bit)}

    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_10_corner_analysis.jpg"), debug_canvas)

    print("  -> Corner Roundness:")
    for k, v in stats.items():
        print(
            f"     * {k.ljust(12)}: {v['missing_paper_area']}px | Whitening = {v['whitening_px']}px")

    return stats


def process_side(path_0, path_180, side_name):
    print(
        f"\n================ PROCESSING {side_name.upper()} ================")
    result_0 = isolate_card(path_0, prefix=f"{side_name}_0deg")
    result_180 = isolate_card(path_180, prefix=f"{side_name}_180deg")

    if result_0 is None or result_180 is None:
        print(f"❌ Failed to isolate {side_name}.")
        return None

    warped_0, warped_mask_0 = result_0
    warped_180, warped_mask_180 = result_180

    centering_stats = analyze_centering(localize_borders(
        warped_0, prefix=f"{side_name}_0deg"), warped_0, prefix=f"{side_name}_0deg")
    edges_0 = segment_edges(warped_0, prefix=f"{side_name}_0deg")
    edges_180 = segment_edges(warped_180, prefix=f"{side_name}_180deg")

    masks_0 = extract_damage_masks(
        edges_0, warped_0, prefix=f"{side_name}_0deg")
    masks_180 = extract_damage_masks(
        edges_180, warped_180, prefix=f"{side_name}_180deg")

    true_masks = filter_true_damage(masks_0, masks_180)
    edge_stats = evaluate_and_visualize_damage(
        true_masks, edges_0, warped_0, prefix=side_name)
    corner_stats = analyze_corners(
        warped_0, warped_mask_0, prefix=f"{side_name}_0deg")

    return {"centering": centering_stats, "edges": edge_stats, "corners": corner_stats}


def run_cv_pipeline(card_prefix, jpeg_dir):
    front_0_path = os.path.join(jpeg_dir, f"{card_prefix}-front.jpg")
    front_180_path = os.path.join(jpeg_dir, f"{card_prefix}-front-rev.jpg")
    back_0_path = os.path.join(jpeg_dir, f"{card_prefix}-back.jpg")
    back_180_path = os.path.join(jpeg_dir, f"{card_prefix}-back-rev.jpg")

    front_data = process_side(front_0_path, front_180_path, "front")
    back_data = process_side(back_0_path, back_180_path, "back")

    return front_data, back_data


def calculate_final_grade(front_data, back_data, surface_grade):
    subgrades = {"centering": 10, "edges": 10,
                 "corners": 10, "surface": int(surface_grade)}

    # --- 1. CENTERING SUBGRADE ---
    subgrades["centering"] = min(
        front_data["centering"]["grade"], back_data["centering"]["grade"])

    # --- 2. EDGE SUBGRADE ---
    total_edge_damage_px = 0
    total_edge_px = 0
    for side in [front_data, back_data]:
        for edge, stats in side["edges"].items():
            total_edge_damage_px += stats["damage_px"]
            total_edge_px += stats["total_px"]

    edge_damage_pct = (total_edge_damage_px / total_edge_px) * 100
    if edge_damage_pct <= 0.5:
        e_grade = 10
    elif edge_damage_pct <= 1.5:
        e_grade = 9
    elif edge_damage_pct <= 3.0:
        e_grade = 8
    elif edge_damage_pct <= 4.5:
        e_grade = 7
    elif edge_damage_pct <= 6.0:
        e_grade = 6
    elif edge_damage_pct <= 8.0:
        e_grade = 5
    elif edge_damage_pct <= 10.0:
        e_grade = 4
    elif edge_damage_pct <= 13.0:
        e_grade = 3
    elif edge_damage_pct <= 18.0:
        e_grade = 2
    else:
        e_grade = 1
    subgrades["edges"] = e_grade

    # --- 3. CORNER SUBGRADE ---
    total_corner_whitening = 0
    corner_shapes_front, corner_shapes_back = [], []
    for side_name, side in [("front", front_data), ("back", back_data)]:
        for corner, stats in side["corners"].items():
            total_corner_whitening += stats["whitening_px"]
            if side_name == "front":
                corner_shapes_front.append(stats["missing_paper_area"])
            else:
                corner_shapes_back.append(stats["missing_paper_area"])

    worst_variance = max(
        max(corner_shapes_front) - min(corner_shapes_front),
        max(corner_shapes_back) - min(corner_shapes_back)
    )

    co_grade = 10
    if total_corner_whitening > 10:
        co_grade = min(co_grade, 9)
    if total_corner_whitening > 100:
        co_grade = min(co_grade, 8)
    if total_corner_whitening > 300:
        co_grade = min(co_grade, 7)
    if total_corner_whitening > 600:
        co_grade = min(co_grade, 6)
    if total_corner_whitening > 1000:
        co_grade = min(co_grade, 5)
    if total_corner_whitening > 1500:
        co_grade = min(co_grade, 4)
    if total_corner_whitening > 2200:
        co_grade = min(co_grade, 3)
    if total_corner_whitening > 3000:
        co_grade = min(co_grade, 2)
    if total_corner_whitening > 4500:
        co_grade = min(co_grade, 1)

    if worst_variance > 250:
        co_grade = min(co_grade, 9)
    if worst_variance > 450:
        co_grade = min(co_grade, 8)
    if worst_variance > 650:
        co_grade = min(co_grade, 7)
    if worst_variance > 900:
        co_grade = min(co_grade, 5)
    if worst_variance > 1200:
        co_grade = min(co_grade, 3)
    if worst_variance > 1500:
        co_grade = min(co_grade, 1)
    subgrades["corners"] = co_grade

    # --- 4. OVERALL GRADE CALCULATION ---
    lowest_sub = min(subgrades.values())
    final_grade = float(lowest_sub)

    if sum(subgrades.values()) >= (lowest_sub * 4) + 2:
        final_grade += 0.5

    if final_grade > (lowest_sub + 0.5):
        final_grade = float(lowest_sub + 0.5)

    if final_grade == 10.0 and sum(subgrades.values()) == 40.0:
        final_grade = "10.0 (PRISTINE)"

    return subgrades, final_grade


# =====================================================================
# STANDALONE DEBUG EXECUTION
# =====================================================================
if __name__ == "__main__":
    print("--- 🔍 SILPHDB CV DEBUGGER ---")

    # Prompt for variables
    card_prefix = input(
        "Enter the card prefix (e.g., 'starmie', '11-BASE1-54-EN-UNL'): ").strip()
    surface_input = input("Enter assumed human surface grade (1-10): ").strip()
    surface_grade = int(surface_input) if surface_input.isdigit() else 9

    # Check for files
    missing = []
    for side in ["front", "front-rev", "back", "back-rev"]:
        path = os.path.join(JPEG_DIR, f"{card_prefix}-{side}.jpg")
        if not os.path.exists(path):
            missing.append(os.path.basename(path))

    if missing:
        print("\n❌ ERROR: Missing the following files in the 'jpegs' directory:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    print(f"\n🚀 Booting Debug Pipeline for [{card_prefix}]...")
    front_data, back_data = run_cv_pipeline(card_prefix, JPEG_DIR)

    if front_data and back_data:
        subgrades, final_grade = calculate_final_grade(
            front_data, back_data, surface_grade)

        print("\n" + "="*50)
        print(f" 🏆 SILPHGRADE FINAL RESULT : {final_grade}")
        print("-" * 50)
        print(f"  SURFACE   : {subgrades['surface']}")
        print(f"  CENTERING : {subgrades['centering']}")
        print(f"  EDGES     : {subgrades['edges']}")
        print(f"  CORNERS   : {subgrades['corners']}")
        print("="*50 + "\n")
        print(f"✅ Debug photos successfully written to: {DEBUG_DIR}")
    else:
        print("\n❌ Pipeline failed to isolate the card.")
