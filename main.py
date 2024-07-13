from config import settings
from workers.stable_difusion_a1111_worker import StableDiffusion


info, images = stable_diffusion_worker.generate("fox, girl, fennec, dress,",
                                                restore_faces=False, tiling=False,
                                                enable_hr=True, hr_scale=1.7,
                                                denoising_strength=0.7, )
print(info["infotexts"])
for i, image in enumerate(images):
    with open(f"image{i}.png", "wb") as file:
        file.write(image)
