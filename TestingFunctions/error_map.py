import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import cv2

# load data
a = pd.read_csv(
    "TestingData/carte_erreur_thermique/FLIR0050_temperatures.csv",
    skiprows=5,
    header=None
).to_numpy()

a_sim = pd.read_csv(
    "TestingData/carte_erreur_thermique/simulation_temperatures_60s.csv",
    skiprows=5,
    header=None
).to_numpy()

b = pd.read_csv(
    "TestingData/carte_erreur_thermique/FLIR0051_temperatures.csv",
    skiprows=5,
    header=None
).to_numpy()

b_sim = pd.read_csv(
    "TestingData/carte_erreur_thermique/simulation_temperatures_final.csv",
    skiprows=5,
    header=None
).to_numpy()

# resizing
a_sim_resized = cv2.resize(a_sim, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_CUBIC)
b_sim_resized = cv2.resize(b_sim, (b.shape[1], b.shape[0]), interpolation=cv2.INTER_CUBIC)

# differences
diff_a = a_sim_resized - a
diff_b = b_sim_resized - b

# ---- COMMON COLOR SCALE ----
vmin = min(diff_a.min(), diff_b.min())
vmax = max(diff_a.max(), diff_b.max())

# plotting
fig, axs = plt.subplots(2, 1)

# Erreur avec une commande de 30°C après 60 s
im1 = axs[0].imshow(diff_a, vmin=vmin, vmax=vmax)

# Erreur avec une commande de 30°C après stabilitsation
im2 = axs[1].imshow(diff_b, vmin=vmin, vmax=vmax)

# single shared colorbar
fig.colorbar(im2, ax=axs)

plt.show()