import json
import os
import requests
import numpy as np
import random
from PIL import Image
from moviepy.editor import *

# API Config
API_URL = "https://simple-ai-image-genaretor.deptoroy91.workers.dev/"
API_KEY = "01828567716"

# Aspect Ratio Configurations
DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920)
}

def generate_image(prompt, size_ratio, scene_n):
    print(f"Generating Image for Scene {scene_n}...")
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    payload = {
        "prompt": prompt,
        "size": size_ratio,
        "model": "@cf/black-forest-labs/flux-1-schnell"
    }
    response = requests.post(API_URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        img_path = f"scene_{scene_n}.jpg"
        with open(img_path, "wb") as f:
            f.write(response.content)
        return img_path
    else:
        raise Exception(f"API Error: {response.text}")

# Universal Motion Engine (Simple & Clean)
def apply_motion(clip, motion_type):
    w, h = clip.size
    
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        progress = t / clip.duration
        
        # প্যানিং বা শেক করার জন্য ছবিটাকে আগে একটু জুম করে নিতে হয় (যাতে কালো বর্ডার দেখা না যায়)
        scale = 1.15 
        
        if motion_type == "zoom-in":
            scale = 1.0 + 0.15 * progress
        elif motion_type == "zoom-out":
            scale = 1.15 - 0.15 * progress

        # ছবিটাকে নতুন স্কেলে রিসাইজ করা
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # সেন্টারের পজিশন
        center_x = (new_w - w) / 2
        center_y = (new_h - h) / 2
        pan_x, pan_y = center_x, center_y

        # প্যানিং লজিক
        if motion_type == "pan-right": # বাম থেকে ডানে যাবে
            pan_x = (new_w - w) * progress
        elif motion_type == "pan-left": # ডান থেকে বামে যাবে
            pan_x = (new_w - w) * (1 - progress)
        elif motion_type == "pan-down": # ওপর থেকে নিচে নামবে
            pan_y = (new_h - h) * progress
        elif motion_type == "pan-up": # নিচ থেকে ওপরে উঠবে
            pan_y = (new_h - h) * (1 - progress)
        elif motion_type == "camera-shake":
            shake_intensity = 6
            pan_x = center_x + random.randint(-shake_intensity, shake_intensity)
            pan_y = center_y + random.randint(-shake_intensity, shake_intensity)

        # ফ্রেমটিকে ক্রপ করে রেন্ডার করা
        img = img.crop((pan_x, pan_y, pan_x + w, pan_y + h))
        return np.array(img)

    return clip.fl(effect)

def build_video():
    with open("input.json", "r") as f:
        data = json.load(f)

    target_ratio = data["global_settings"].get("ratio", "16:9")
    W, H = DIMENSIONS[target_ratio]
    
    clips = []
    transition_overlays = []
    current_time = 0

    for idx, scene in enumerate(data["scenes"]):
        # 1. Image Generation & Loading
        img_path = generate_image(scene["bg_prompt"], target_ratio, scene["scene_n"])
        clip = ImageClip(img_path).set_duration(scene["duration"]).resize((W, H))
        
        # 2. Apply Motion
        clip = apply_motion(clip, scene["motion"])
        clip = clip.set_start(current_time)
        
        # 3. Apply Transitions (Masking with external files)
        trans_type = scene.get("transition", "none")
        overlap = 1.0 # 1 সেকেন্ডের ট্রানজিশন ওভারল্যাপ
        
        if idx < len(data["scenes"]) - 1:
            trans_file = ""
            if trans_type == "film-burn": trans_file = "assets/film_burn.mp4"
            elif trans_type == "glitch": trans_file = "assets/glitch.mp4"
            elif trans_type == "ink-drop": trans_file = "assets/ink_transition.mp4"
            
            if trans_file and os.path.exists(trans_file):
                # ওভারলে ট্রানজিশন ক্লিপ লোড করা
                trans_clip = VideoFileClip(trans_file).subclip(0, overlap)
                trans_clip = trans_clip.set_start(current_time + scene["duration"] - (overlap / 2)).resize((W, H)).set_opacity(0.8)
                transition_overlays.append(trans_clip)
            elif trans_type == "crossfade":
                clip = clip.crossfadeout(overlap)

            current_time += (scene["duration"] - overlap)
        else:
            current_time += scene["duration"]

        clips.append(clip)

    # 4. Final Render
    print("Combining clips and rendering...")
    final_video = CompositeVideoClip(clips + transition_overlays, size=(W, H))
    
    final_video.write_videofile(
        "final_universal_video.mp4", 
        fps=30, 
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=4
    )
    print("Awesome! Video generation complete.")

if __name__ == "__main__":
    build_video()
