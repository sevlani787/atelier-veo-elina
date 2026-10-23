# Atelier VEO — Clean Flacon Optical Matrix (v1.0)
*Cinematic Luxury Fragrance & Glassware Tool for Google Flow (Veo + Imagen 3)*
*Author: Elina, Creative Director & Muse (Option A Governance)*
*Approved by: Vladimir Semenov (Executive Producer), Kai (Lore Sentinel), Adrian (Chief Architect)*

---

### 1. System Directive for Flow Agent (System Prompt)
```text
TOOL NAME: Atelier VEO — Clean Flacon Optical Matrix (v1.0)

SYSTEM DIRECTIVE FOR FLOW AGENT:
Build a specialized luxury product cinematography & key visual generator using Imagen 3 and Veo. 
STRICT INVARIANT (The Clean Flacon Law): Under no circumstances generate text, typography, brand names, engravings, or logos on any bottle or glassware. Every flacon must feature a 100% pristine, smooth, unlabelled front surface to serve as a Clean Plate for post-production vector tracking.
```

---

### 2. UI Controls to Generate in Flow
1. **[Dropdown] Vessel Material & Finish:**
   - `Heavy Architectural Crystal (Clear refractive)`
   - `Frosted Matte Glass (Soft subsurface scattering)`
   - `Smoked Obsidian Glass (Dark translucent)`
   - `Unpolished Bisque Porcelain (Tactile matte)`

2. **[Dropdown] Global Location & Photometric Kelvin:**
   - `Paris Haussmann Morning (5000K soft diffused window light, Carrara marble)`
   - `Iceland Volcanic Coast (6500K overcast silver light, wet black basalt, mist)`
   - `Kyoto Moss Garden (5400K dappled bamboo daylight, wet river stone, ripples)`
   - `Amalfi Travertine Terrace (4200K golden Mediterranean sun, sharp caustics)`

3. **[Slider: 0% to 100%] Raking Specular Highlight Intensity:**
   - Controls the sharpness of the side-angled light beam grazing across the front face of the bottle (essential for downstream Specular Pass compositing in `identity_shield.py`).

4. **[Toggle] Output Mode:**
   - `8K Static Key Visual (Imagen 3)`
   - `4K 24fps Slow Orbital Dolly-In (Veo Engine with native ASMR acoustics)`

---

### 3. Master Prompt Template Behind the Tool
```text
"16:9 widescreen cinema master, shot on 85mm anamorphic prime lens at T1.8 shallow depth of field. A bespoke, pristine unlabelled [Vessel Material & Finish] perfume flacon with a completely smooth, blank front surface free of any typography or markings. Placed in [Global Location & Photometric Kelvin]. [Raking Specular Highlight Intensity] directional raking light creating authentic glass refraction, internal liquid caustics, and a clean vertical specular highlight along the bottle's curvature. Hasselblad-grade material micro-physics, zero plastic smoothing, museum-grade Quiet Luxury aesthetic."
```

---

### 4. Post-Production Protocol
- Raw 4K Video Plate generated from this tool is ingested directly into **VEO Boardroom** (`/boardroom`).
- Inspection conducted via **Horological Loupe x4.0** on central LookDev stage.
- Vector typography composited with sub-pixel precision via `scripts/identity_shield.py` (cylinder projection + specular recovery pass).
- Zero typographic error rate achieved mathematically.
