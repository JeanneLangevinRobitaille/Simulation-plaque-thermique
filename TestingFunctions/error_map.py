import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import cv2

# données expérimentales
a = pd.read_csv(
    "TestingData/carte_erreur_thermique/FLIR0050_temperatures.csv",
    skiprows=5,
    header=None
).to_numpy()

b = pd.read_csv(
    "TestingData/carte_erreur_thermique/FLIR0051_temperatures.csv",
    skiprows=5,
    header=None
).to_numpy()

# données simulées
a_sim = pd.read_csv(
    "TestingData/carte_erreur_thermique/simulation_temperatures_60s.csv",
    skiprows=5,
    header=None
).to_numpy()

b_sim = pd.read_csv(
    "TestingData/carte_erreur_thermique/simulation_temperatures_final.csv",
    skiprows=5,
    header=None
).to_numpy()

# resizing
a_sim_resized = cv2.resize(
    a_sim, (a.shape[1], a.shape[0]), 
    interpolation=cv2.INTER_CUBIC)

b_sim_resized = cv2.resize(
    b_sim, (b.shape[1], b.shape[0]), 
    interpolation=cv2.INTER_CUBIC)

# différences
diff_a = a_sim_resized - a
diff_b = b_sim_resized - b

# échelles
vmin_cam = min(a.min(), b.min())
vmax_cam = max(a.max(), b.max())

vmax_err = max(abs(diff_a).max(), abs(diff_b).max())
vmin_err = -vmax_err

# ==== plotting ====
fig, axs = plt.subplots(2, 2, figsize=(10, 6))

# ajustement pour laisser de la place à droite
plt.subplots_adjust(right=0.88, wspace=0.05, hspace=0.1)

# --- 60 s ---
axs[0, 0].imshow(a, cmap="gray", vmin=vmin_cam, vmax=vmax_cam)
im_err = axs[0, 1].imshow(diff_a, vmin=vmin_err, vmax=vmax_err)

# --- stabilisé ---
axs[1, 0].imshow(b, cmap="gray", vmin=vmin_cam, vmax=vmax_cam)
axs[1, 1].imshow(diff_b, vmin=vmin_err, vmax=vmax_err)

# enlever axes
for ax in axs.flat:
    ax.axis("off")

# ==== COLORBAR externe pleine hauteur ====
cbar_ax = fig.add_axes([0.90, 0.15, 0.02, 0.7])
fig.colorbar(im_err, cax=cbar_ax, label="Erreur (°C)")


plt.show()