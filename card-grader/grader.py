import cv2
import numpy as np
import os

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
    except Exception as e:
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

    if prefix == "front":
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

    # NEW: Warp the binary silhouette mask so Phase 7 knows exactly where the background is!
    warped_mask = cv2.warpPerspective(closed, M, (CARD_WIDTH, CARD_HEIGHT))

    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_05_warped_final.jpg"), warped)

    return warped, warped_mask


def localize_borders(warped_img, prefix="front"):
    img_h, img_w = warped_img.shape[:2]

    PCT_LR = 0.10
    PCT_TB = 0.10

    left_bound = int(img_w * PCT_LR)
    right_bound = int(img_w * (1 - PCT_LR))
    top_bound = int(img_h * PCT_TB)
    bottom_bound = int(img_h * (1 - PCT_TB))

    # Shave off 20% to avoid corners
    y_margin = int(img_h * 0.20)
    x_margin = int(img_w * 0.20)

    regions = {
        "left_strip": warped_img[y_margin: img_h - y_margin, 0: left_bound],
        "right_strip": warped_img[y_margin: img_h - y_margin, right_bound: img_w],
        "top_strip": warped_img[0: top_bound, x_margin: img_w - x_margin],
        "bottom_strip": warped_img[bottom_bound: img_h, x_margin: img_w - x_margin]
    }
    return regions

# --- THE FIX: COLOR-AWARE SCANNER ---


# --- PHASE 4: THE TARGET LOCK SCANNER (V8) ---
def find_border_width(strip_img, prefix="front", is_vertical=False, reverse=False):
    # Tiny blur to kill camera grain
    blurred_strip = cv2.GaussianBlur(strip_img, (3, 3), 0)

    # Front uses 80th Percentile to look through text.
    # Back uses 50th (Median) to help ignore surface scuffs.
    percentile_val = 80 if prefix == "front" else 50

    if is_vertical:
        profile_bgr = np.percentile(
            blurred_strip, percentile_val, axis=1).astype(np.float32)
    else:
        profile_bgr = np.percentile(
            blurred_strip, percentile_val, axis=0).astype(np.float32)

    if reverse:
        profile_bgr = profile_bgr[::-1]

    # 1. Find the "True Border Color" by sampling deep inside the safe zone (pixels 20-30).
    # This completely bypasses any heavy physical edge wear on the outside.
    safe_zone = profile_bgr[20:30]
    true_bgr = np.median(safe_zone, axis=0)
    true_hsv = cv2.cvtColor(np.uint8([[true_bgr]]), cv2.COLOR_BGR2HSV)[0][0]

    # 2. Calculate dynamic noise threshold from the healthy safe zone
    base_noise = np.std(safe_zone, axis=0).sum()
    trigger_threshold = max(30.0, base_noise * 3.0)

    locked_on_border = False
    rolling_buffer = []

    # 3. Start scanning from the outer edge
    for i in range(5, len(profile_bgr)):
        curr_bgr = profile_bgr[i]
        curr_hsv = cv2.cvtColor(
            np.uint8([[curr_bgr]]), cv2.COLOR_BGR2HSV)[0][0]
        curr_h, curr_s = int(curr_hsv[0]), int(curr_hsv[1])

        if not locked_on_border:
            # We are unarmed. Check if we have stepped onto the healthy border yet.
            true_h_val, true_s_val = int(true_hsv[0]), int(true_hsv[1])
            hue_diff = abs(curr_h - true_h_val)
            if hue_diff > 90:
                hue_diff = 180 - hue_diff
            color_diff = np.sqrt(((hue_diff) * 2)**2 +
                                 (curr_s - true_s_val)**2)

            # If the current pixel matches the True Border Color, LOCK ON!
            if color_diff < 30:
                locked_on_border = True
                # Initialize memory with healthy pixels
                rolling_buffer = [curr_bgr] * 5
        else:
            # WE ARE LOCKED ON. Now look for the massive color shift of the inner art box!
            base_bgr = np.median(rolling_buffer, axis=0).astype(np.uint8)
            base_hsv = cv2.cvtColor(
                np.uint8([[base_bgr]]), cv2.COLOR_BGR2HSV)[0][0]

            base_h_val, base_s_val = int(base_hsv[0]), int(base_hsv[1])
            hue_diff = abs(curr_h - base_h_val)
            if hue_diff > 90:
                hue_diff = 180 - hue_diff
            color_diff = np.sqrt(((hue_diff) * 2)**2 +
                                 (curr_s - base_s_val)**2)

            if color_diff > trigger_threshold:
                return i  # Cliff detected! Return exact pixel distance.
            else:
                # Still on the border. Keep updating memory to adapt to gentle shadows.
                rolling_buffer.append(curr_bgr)
                if len(rolling_buffer) > 10:
                    rolling_buffer.pop(0)

    return 15  # Failsafe


# --- PHASE 5: EDGE SEGMENTATION (WITH MEMORY FIX) ---
def segment_edges(warped_img, prefix="front"):
    print(f"\n--- Phase 5: Edge Segmentation ({prefix.upper()}) ---")
    img_h, img_w = warped_img.shape[:2]

    # Define the damage zone
    EDGE_MARGIN = 23

    # THE FIX: Add .copy() to force Numpy to create continuous memory blocks!
    # This completely prevents OpenCV C++ exceptions downstream.
    edges = {
        "top": warped_img[0:EDGE_MARGIN, EDGE_MARGIN: img_w - EDGE_MARGIN].copy(),
        "bottom": warped_img[img_h - EDGE_MARGIN: img_h, EDGE_MARGIN: img_w - EDGE_MARGIN].copy(),
        "left": warped_img[EDGE_MARGIN: img_h - EDGE_MARGIN, 0:EDGE_MARGIN].copy(),
        "right": warped_img[EDGE_MARGIN: img_h - EDGE_MARGIN, img_w - EDGE_MARGIN: img_w].copy()
    }

    # 2. Visual Debugger: The "Hollow Frame"
    debug_img = warped_img.copy()

    # Black out the entire center of the card
    cv2.rectangle(debug_img,
                  (EDGE_MARGIN, EDGE_MARGIN),
                  (img_w - EDGE_MARGIN, img_h - EDGE_MARGIN),
                  (0, 0, 0), -1)

    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_08_edge_segmentation.jpg"), debug_img)
    print("  -> Extracted damage zones. Visual frame saved.")

    return edges


def analyze_centering(regions, warped_img, prefix="front"):
    print(f"\n--- Phase 4: Centering Analysis ({prefix.upper()}) ---")

    # We now pass the 'prefix' into the laser scanner so it knows which mode to use!
    left_w = find_border_width(
        regions["left_strip"], prefix, is_vertical=False, reverse=False)
    right_w = find_border_width(
        regions["right_strip"], prefix, is_vertical=False, reverse=True)
    top_w = find_border_width(
        regions["top_strip"], prefix, is_vertical=True, reverse=False)
    bottom_w = find_border_width(
        regions["bottom_strip"], prefix, is_vertical=True, reverse=True)

    print(f"Measured Left: {left_w}px | Right: {right_w}px")
    print(f"Measured Top:  {top_w}px | Bottom: {bottom_w}px")

    lr_total = left_w + right_w
    tb_total = top_w + bottom_w

    lr_worst = max(left_w, right_w)
    lr_ratio = (lr_worst / lr_total) * 100

    tb_worst = max(top_w, bottom_w)
    tb_ratio = (tb_worst / tb_total) * 100

    print(f"\nResults:")
    print(f"L/R Centering: {lr_worst}/{lr_total - lr_worst} ({lr_ratio:.1f}%)")
    print(f"T/B Centering: {tb_worst}/{tb_total - tb_worst} ({tb_ratio:.1f}%)")

    worst_overall = max(lr_ratio, tb_ratio)

    grade = 6
    if worst_overall <= 60:
        grade = 10
    elif worst_overall <= 65:
        grade = 9
    elif worst_overall <= 70:
        grade = 8
    elif worst_overall <= 75:
        grade = 7

    print(f"\n---> Estimated PSA Centering Grade: {grade}")

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

    # NEW: Return the data so Phase 8 can use it!
    return {"grade": grade, "worst_ratio": worst_overall}

# --- PHASE 6: DEEP SAFE ZONE EXTRACTION (WITH VISUAL DEBUGGER) ---


def extract_damage_masks(edges, warped_img, prefix="front"):
    masks = {}

    # Create a copy for the Yellow RAW debugger
    debug_img = warped_img.copy()
    EDGE_MARGIN = 23
    img_h, img_w = warped_img.shape[:2]

    for edge_name, strip in edges.items():
        # Copy the strip so we don't accidentally paint yellow on the real image data yet
        strip_copy = strip.copy()
        blurred = cv2.GaussianBlur(strip_copy, (3, 3), 0)

        if edge_name == "top":
            safe_bgr = blurred[18:23, :]
            base_bgr = np.tile(np.median(safe_bgr, axis=0), (23, 1, 1))
        elif edge_name == "bottom":
            safe_bgr = blurred[0:5, :]
            base_bgr = np.tile(np.median(safe_bgr, axis=0), (23, 1, 1))
        elif edge_name == "left":
            safe_bgr = blurred[:, 18:23]
            base_bgr = np.tile(np.median(safe_bgr, axis=1)[
                               :, np.newaxis, :], (1, 23, 1))
        elif edge_name == "right":
            safe_bgr = blurred[:, 0:5]
            base_bgr = np.tile(np.median(safe_bgr, axis=1)[
                               :, np.newaxis, :], (1, 23, 1))

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

        # --- VISUALIZE RAW UNFILTERED HITS IN YELLOW ---
        yellow_strip = np.zeros_like(strip_copy)
        yellow_strip[:] = (0, 255, 255)  # BGR Yellow
        np.copyto(strip_copy, yellow_strip,
                  where=mask_8bit.astype(bool)[:, :, None])

        if edge_name == "top":
            debug_img[0:EDGE_MARGIN, EDGE_MARGIN: img_w -
                      EDGE_MARGIN] = strip_copy
        elif edge_name == "bottom":
            debug_img[img_h - EDGE_MARGIN: img_h,
                      EDGE_MARGIN: img_w - EDGE_MARGIN] = strip_copy
        elif edge_name == "left":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN,
                      0:EDGE_MARGIN] = strip_copy
        elif edge_name == "right":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN,
                      img_w - EDGE_MARGIN: img_w] = strip_copy

    cv2.rectangle(debug_img,
                  (EDGE_MARGIN, EDGE_MARGIN),
                  (img_w - EDGE_MARGIN, img_h - EDGE_MARGIN),
                  (0, 0, 0), -1)

    # Save the RAW unverified hits
    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_09a_RAW_whitening.jpg"), debug_img)

    return masks


# --- PHASE 6.5: THE INTERSECTION OF TRUTH ---
def filter_true_damage(masks_0, masks_180):
    print("  -> Cross-referencing 0-deg and 180-deg scans to eliminate glare...")
    true_masks = {}

    # We flip the 180-deg masks by "-1" (which flips both Vertically AND Horizontally)
    # This perfectly geometrically aligns the physical edges of the upside-down card
    # to the right-side-up card.
    true_masks["top"] = cv2.bitwise_and(
        masks_0["top"], cv2.flip(masks_180["bottom"], -1))
    true_masks["bottom"] = cv2.bitwise_and(
        masks_0["bottom"], cv2.flip(masks_180["top"], -1))
    true_masks["left"] = cv2.bitwise_and(
        masks_0["left"], cv2.flip(masks_180["right"], -1))
    true_masks["right"] = cv2.bitwise_and(
        masks_0["right"], cv2.flip(masks_180["left"], -1))

    return true_masks


# --- PHASE 6.7: EVALUATION & VISUALIZATION ---
def evaluate_and_visualize_damage(true_masks, edges_0, warped_img_0, prefix="front"):
    print(
        f"\n--- Phase 6: True Edge Whitening Analysis ({prefix.upper()}) ---")
    damage_stats = {}
    total_damage_px = 0
    total_edge_px = 0

    debug_img = warped_img_0.copy()
    EDGE_MARGIN = 23
    img_h, img_w = warped_img_0.shape[:2]

    for edge_name, mask in true_masks.items():
        # We only paint on the 0-degree image so you have a nice right-side-up reference
        strip = edges_0[edge_name]

        damage_px = cv2.countNonZero(mask)
        total_px = strip.shape[0] * strip.shape[1]

        damage_stats[edge_name] = {
            "damage_px": damage_px,
            "total_px": total_px,
            "percent": (damage_px / total_px) * 100
        }

        total_damage_px += damage_px
        total_edge_px += total_px

        red_strip = np.zeros_like(strip)
        red_strip[:] = (0, 0, 255)
        np.copyto(strip, red_strip, where=mask.astype(bool)[:, :, None])

        if edge_name == "top":
            debug_img[0:EDGE_MARGIN, EDGE_MARGIN: img_w - EDGE_MARGIN] = strip
        elif edge_name == "bottom":
            debug_img[img_h - EDGE_MARGIN: img_h,
                      EDGE_MARGIN: img_w - EDGE_MARGIN] = strip
        elif edge_name == "left":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN, 0:EDGE_MARGIN] = strip
        elif edge_name == "right":
            debug_img[EDGE_MARGIN: img_h - EDGE_MARGIN,
                      img_w - EDGE_MARGIN: img_w] = strip

    cv2.rectangle(debug_img,
                  (EDGE_MARGIN, EDGE_MARGIN),
                  (img_w - EDGE_MARGIN, img_h - EDGE_MARGIN),
                  (0, 0, 0), -1)

    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_09_true_whitening_damage.jpg"), debug_img)

    overall_pct = (total_damage_px / total_edge_px) * 100
    print(
        f"Overall True Edge Whitening: {overall_pct:.2f}% ({total_damage_px} pixels)")
    for k, val in damage_stats.items():
        print(f"  -> {k.capitalize()}: {val['percent']:.2f}%")

    print("  -> True damage visualization saved.")
    return damage_stats

# --- PHASE 7: CORNER ANALYSIS ---


# --- PHASE 7: CORNER ANALYSIS ---
# --- PHASE 7: CORNER ANALYSIS (MASK-AWARE V2) ---
def analyze_corners(warped_img, warped_mask, prefix="front"):
    print(f"\n--- Phase 7: Corner Analysis ({prefix.upper()}) ---")

    CORNER_SIZE = 60
    img_h, img_w = warped_img.shape[:2]

    corners = {
        "top_left": warped_img[0:CORNER_SIZE, 0:CORNER_SIZE].copy(),
        "top_right": warped_img[0:CORNER_SIZE, img_w-CORNER_SIZE:img_w].copy(),
        "bottom_left": warped_img[img_h-CORNER_SIZE:img_h, 0:CORNER_SIZE].copy(),
        "bottom_right": warped_img[img_h-CORNER_SIZE:img_h, img_w-CORNER_SIZE:img_w].copy()
    }

    # Extract the exact matching 60x60 crops from the Phase 1 Silhouette Mask
    corner_masks = {
        "top_left": warped_mask[0:CORNER_SIZE, 0:CORNER_SIZE],
        "top_right": warped_mask[0:CORNER_SIZE, img_w-CORNER_SIZE:img_w],
        "bottom_left": warped_mask[img_h-CORNER_SIZE:img_h, 0:CORNER_SIZE],
        "bottom_right": warped_mask[img_h-CORNER_SIZE:img_h, img_w-CORNER_SIZE:img_w]
    }

    stats = {}
    debug_canvas = np.zeros_like(warped_img)

    for name, corner in corners.items():
        silhouette = corner_masks[name]

        # 1. MEASURE DEFORMATION (The Black Triangle)
        # We don't guess grayscale anymore. Phase 1 already proved these pixels are playmat!
        black_mask = (silhouette == 0)

        # 2. MEASURE WHITENING
        hsv = cv2.cvtColor(corner, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        gray = cv2.cvtColor(corner, cv2.COLOR_BGR2GRAY)

        if "front" in prefix:
            white_mask = (s < 50) & (v > 150) & (gray > 130)
        else:
            white_mask = (s < 50) & (v > 150)

        # CRITICAL FIX: Only scan for whitening on pixels that Phase 1 confirmed are Cardboard!
        # This completely erases playmat glare from the whitening score.
        white_mask = white_mask & (silhouette == 255)

        white_mask_8bit = np.where(white_mask, 255, 0).astype(np.uint8)
        black_mask_8bit = np.where(black_mask, 255, 0).astype(np.uint8)

        # 3. METRICS
        black_area = cv2.countNonZero(black_mask_8bit)
        white_area = cv2.countNonZero(white_mask_8bit)

        stats[name] = {
            "missing_paper_area": black_area,
            "whitening_px": white_area
        }

        # 4. PAINT DEBUGGER
        blue_overlay = np.zeros_like(corner)
        blue_overlay[:] = (255, 0, 0)
        np.copyto(corner, blue_overlay,
                  where=black_mask[:, :, None])  # <-- FIX HERE

        red_overlay = np.zeros_like(corner)
        red_overlay[:] = (0, 0, 255)
        np.copyto(corner, red_overlay,
                  where=white_mask[:, :, None])  # <-- FIX HERE

        if name == "top_left":
            debug_canvas[0:CORNER_SIZE, 0:CORNER_SIZE] = corner
        elif name == "top_right":
            debug_canvas[0:CORNER_SIZE, img_w-CORNER_SIZE:img_w] = corner
        elif name == "bottom_left":
            debug_canvas[img_h-CORNER_SIZE:img_h, 0:CORNER_SIZE] = corner
        elif name == "bottom_right":
            debug_canvas[img_h-CORNER_SIZE:img_h,
                         img_w-CORNER_SIZE:img_w] = corner

    cv2.imwrite(os.path.join(
        DEBUG_DIR, f"{prefix}_10_corner_analysis.jpg"), debug_canvas)

    print("  -> Corner Roundness (Ideal Gem Mint ~ 150px to 200px):")
    for k, v in stats.items():
        print(
            f"     * {k.ljust(12)}: {v['missing_paper_area']}px | Whitening = {v['whitening_px']}px")

    return stats

# --- PHASE 8: THE FINAL GRADE ---


# --- PHASE 8: THE FINAL GRADE (FULL 1-10 SCALE) ---
def generate_final_report(front_data, back_data):
    print("\n" + "="*50)
    print(" 🏆 SILPHDB AUTOMATED GRADING REPORT 🏆")
    print("="*50)

    subgrades = {"centering": 10, "edges": 10, "corners": 10}

    # --- 1. CENTERING SUBGRADE ---
    c_grade = min(front_data["centering"]["grade"],
                  back_data["centering"]["grade"])
    subgrades["centering"] = c_grade

    # --- 2. EDGE SUBGRADE ---
    total_edge_damage_px = 0
    total_edge_px = 0

    for side in [front_data, back_data]:
        for edge, stats in side["edges"].items():
            total_edge_damage_px += stats["damage_px"]
            total_edge_px += stats["total_px"]

    edge_damage_pct = (total_edge_damage_px / total_edge_px) * 100

    # Extended 1-10 Scale for Edges
    if edge_damage_pct <= 0.5:
        e_grade = 10
    elif edge_damage_pct <= 1.5:
        e_grade = 9
    elif edge_damage_pct <= 3.5:
        e_grade = 8
    elif edge_damage_pct <= 6.0:
        e_grade = 7
    elif edge_damage_pct <= 10.0:
        e_grade = 6
    elif edge_damage_pct <= 15.0:
        e_grade = 5
    elif edge_damage_pct <= 20.0:
        e_grade = 4
    elif edge_damage_pct <= 25.0:
        e_grade = 3
    elif edge_damage_pct <= 30.0:
        e_grade = 2
    else:
        e_grade = 1

    subgrades["edges"] = e_grade

    # --- 3. CORNER SUBGRADE ---
    total_corner_whitening = 0
    corner_shapes_front = []
    corner_shapes_back = []

    for side_name, side in [("front", front_data), ("back", back_data)]:
        for corner, stats in side["corners"].items():
            total_corner_whitening += stats["whitening_px"]
            if side_name == "front":
                corner_shapes_front.append(stats["missing_paper_area"])
            else:
                corner_shapes_back.append(stats["missing_paper_area"])

    variance_front = max(corner_shapes_front) - min(corner_shapes_front)
    variance_back = max(corner_shapes_back) - min(corner_shapes_back)
    worst_variance = max(variance_front, variance_back)

    co_grade = 10

    # Extended Whitening Deductions
    if total_corner_whitening > 10:
        co_grade = min(co_grade, 9)
    if total_corner_whitening > 100:
        co_grade = min(co_grade, 8)
    if total_corner_whitening > 300:
        co_grade = min(co_grade, 7)
    if total_corner_whitening > 1000:
        co_grade = min(co_grade, 6)
    if total_corner_whitening > 2500:
        co_grade = min(co_grade, 5)
    if total_corner_whitening > 5000:
        co_grade = min(co_grade, 4)
    if total_corner_whitening > 8000:
        co_grade = min(co_grade, 3)
    if total_corner_whitening > 12000:
        co_grade = min(co_grade, 2)
    if total_corner_whitening > 18000:
        co_grade = min(co_grade, 1)

    # Extended Deformation (Shape Variance) Deductions
    if worst_variance > 75:
        co_grade = min(co_grade, 9)
    if worst_variance > 150:
        co_grade = min(co_grade, 8)
    if worst_variance > 250:
        co_grade = min(co_grade, 7)
    if worst_variance > 400:
        co_grade = min(co_grade, 5)
    if worst_variance > 600:
        co_grade = min(co_grade, 3)
    if worst_variance > 800:
        co_grade = min(co_grade, 1)

    subgrades["corners"] = co_grade

    # --- 4. OVERALL GRADE CALCULATION ---
    lowest_sub = min(subgrades.values())

    bump_eligible = sum(subgrades.values()) - \
        lowest_sub >= (lowest_sub + 1.5) * 2

    final_grade = float(lowest_sub)
    if bump_eligible and lowest_sub < 10:
        final_grade += 0.5

    if final_grade == 10.0 and sum(subgrades.values()) == 30:
        final_grade = "10.0 (PRISTINE)"

    print(f"  CENTERING : {subgrades['centering']}")
    print(f"  EDGES     : {subgrades['edges']}  ({edge_damage_pct:.2f}% wear)")
    print(
        f"  CORNERS   : {subgrades['corners']}  ({worst_variance}px variance, {total_corner_whitening}px wear)")
    print("-" * 50)
    print(f"  FINAL GRADE : {final_grade}")
    print("=" * 50 + "\n")


# --- MAIN EXECUTION ---
# File paths
front_0_path = os.path.join(JPEG_DIR, "starmie-front.jpg")
front_180_path = os.path.join(JPEG_DIR, "starmie-front-rev.jpg")
back_0_path = os.path.join(JPEG_DIR, "starmie-back.jpg")
back_180_path = os.path.join(JPEG_DIR, "starmie-back-rev.jpg")


def process_side(path_0, path_180, side_name):
    print(
        f"\n================ PROCESSING {side_name.upper()} ================")

    result_0 = isolate_card(path_0, prefix=f"{side_name}_0deg")
    result_180 = isolate_card(path_180, prefix=f"{side_name}_180deg")

    if result_0 is None or result_180 is None:
        print(f"Failed to isolate {side_name}.")
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

    # NEW: Return all the aggregated data for this side!
    return {
        "centering": centering_stats,
        "edges": edge_stats,
        "corners": corner_stats
    }


# Run the pipeline and capture the data
front_data = process_side(front_0_path, front_180_path, "front")
back_data = process_side(back_0_path, back_180_path, "back")

# Generate the final official grade
if front_data and back_data:
    generate_final_report(front_data, back_data)
else:
    print("\nCould not generate final report due to isolation errors.")
