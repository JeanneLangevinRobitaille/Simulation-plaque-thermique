import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
from tkinter import ttk

# ==========================
# Fenêtre principale
# ==========================
root = tk.Tk()
root.title("Simulateur de plaque asservie en température")
root.geometry('1200x900')

running = False
data_out = None
results_out = None

# ==========================
# Paramètres
# ==========================
params = {
    "L_mm": tk.DoubleVar(value=117.5),
    "l_mm": tk.DoubleVar(value=61.5),
    "e_mm": tk.DoubleVar(value=1.7),
    "P_W": tk.DoubleVar(value=1.0),
    "t_s": tk.DoubleVar(value=150),
    "res": tk.DoubleVar(value=50),
    "T0_C": tk.DoubleVar(value=20),
    "Tamb_C": tk.DoubleVar(value=20),
    "alpha": tk.DoubleVar(value=97),
    "rho": tk.DoubleVar(value=2.7e-3),
    "Cp": tk.DoubleVar(value=0.9),
    "h": tk.DoubleVar(value=5e-5),
    "coord_T1": tk.StringVar(value="(0,0)"),
    "coord_T2": tk.StringVar(value="(0,0)"),
    "coord_T3": tk.StringVar(value="(0,0)"),
    "coord_Resistance": tk.StringVar(value="(0,0)"),
    "val_Resistance": tk.DoubleVar(value=0.0)
}

# ==========================
# Fonctions affichage
# ==========================
def section_title(parent, text):
    ttk.Label(parent, text=text,
              font=("Arial", 11, "bold")).pack(anchor="w", pady=(10, 4))

def field(parent, row, label, var, unit):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(5, 10))
    ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=1)
    ttk.Label(parent, text=unit).grid(row=row, column=2, padx=5)

def coord_field(parent, row, label, var, unit):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(5, 10))
    ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=1)
    ttk.Label(parent, text=unit).grid(row=row, column=2, padx=5)

# ==========================
# Texte en haut
# ==========================
header_frame = ttk.Frame(root)
header_frame.pack(fill="x", pady=(15, 10))

ttk.Label(header_frame,
          text="Appuyer sur Go pour activer la simulation",
          font=("Arial", 11, "italic")).pack()

ttk.Label(header_frame,
          text="Appuyer sur Cancel pour l'interrompre et/ou changer ses paramètres",
          font=("Arial", 11, "italic")).pack()

ttk.Label(header_frame,
          text="Fermer la fenêtre pour sauvegarder les données brutes de la simulation",
          font=("Arial", 11, "italic")).pack()

ttk.Separator(root, orient="horizontal").pack(fill="x", pady=10)

# ==========================
# Structure principale
# ==========================
main_frame = ttk.Frame(root)
main_frame.pack(fill="both", expand=True, padx=30)

main_frame.columnconfigure(0, weight=3)
main_frame.columnconfigure(1, weight=1)

# ==========================
# COLONNE GAUCHE
# ==========================
left_frame = ttk.Frame(main_frame)
left_frame.grid(row=0, column=0, sticky="nw")

section_title(left_frame, "Paramètres de la plaque")
frame_geo = ttk.Frame(left_frame)
frame_geo.pack(anchor="w")
frame_geo.grid_columnconfigure(0, weight=1)

field(frame_geo, 0, "Longueur", params["L_mm"], "mm")
field(frame_geo, 1, "Largeur", params["l_mm"], "mm")
field(frame_geo, 2, "Épaisseur", params["e_mm"], "mm")

section_title(left_frame, "Paramètres de la simulation")
frame_sim = ttk.Frame(left_frame)
frame_sim.pack(anchor="w")
frame_sim.grid_columnconfigure(0, weight=1)

field(frame_sim, 0, "Puissance entrée", params["P_W"], "W")
field(frame_sim, 1, "Temps simulation", params["t_s"], "s")
field(frame_sim, 2, "Résolution", params["res"], "N x N")
field(frame_sim, 3, "Température initiale", params["T0_C"], "°C")
field(frame_sim, 4, "Température ambiante", params["Tamb_C"], "°C")

section_title(left_frame, "Paramètres physiques")
frame_phys = ttk.Frame(left_frame)
frame_phys.pack(anchor="w")
frame_phys.grid_columnconfigure(0, weight=1)

field(frame_phys, 0, "α (diffusivité)", params["alpha"], "mm²/s")
field(frame_phys, 1, "ρ (densité)", params["rho"], "kg/mm³")
field(frame_phys, 2, "Cp (calorifique massique)", params["Cp"], "J/mg·K")
field(frame_phys, 3, "h (convection)", params["h"], "W/mm²·K")

# ==========================
# COLONNE DROITE
# ==========================
right_frame = ttk.Frame(main_frame)
right_frame.grid(row=0, column=1, sticky="nw", padx=(40,0))

section_title(right_frame, "Coordonnées d'intérêt")
frame_coords = ttk.Frame(right_frame)
frame_coords.pack(anchor="w")
frame_coords.grid_columnconfigure(0, weight=1)

coord_field(frame_coords, 0, "T1", params["coord_T1"], "(x,y)")
coord_field(frame_coords, 1, "T2", params["coord_T2"], "(x,y)")
coord_field(frame_coords, 2, "T3", params["coord_T3"], "(x,y)")

section_title(right_frame, "Perturbation")
frame_pert = ttk.Frame(right_frame)
frame_pert.pack(anchor="w")
frame_pert.grid_columnconfigure(0, weight=1)

coord_field(frame_pert, 0, "Coordonnées", params["coord_Resistance"], "(x,y)")
coord_field(frame_pert, 1, "Valeur", params["val_Resistance"], "ohm")

# ==========================
# Simulation thermique
# ==========================
def simulation(data):
    global running, data_out, results_out

    input_power = data["P_W"]
    start_temp = data["T0_C"]
    sim_time = data["t_s"]
    resolution = int(data["res"])

    width = data["l_mm"]
    length = data["L_mm"]
    thickness = data["e_mm"]
    alpha = data["alpha"]
    rho = data["rho"]
    cp = data["Cp"]
    h = data["h"]
    T_amb = data["Tamb_C"]

    x = np.linspace(-width/2, width/2, resolution+1)
    y = np.linspace(0, length, resolution+1)
    X, Y = np.meshgrid(x, y)

    T = np.full_like(X, start_temp, dtype=float)
    Tn = T.copy()

    dx = width / resolution
    dy = length / resolution
    centre = resolution // 2

    dt = 0.2 * min(dx, dy)**2 / alpha
    steps_per_frame = 200

    volume_entree = (2*dx)*(2*dy)*thickness
    Q_entree = input_power / volume_entree

    temps, Tin, Tmid, Tout = [], [], [], []

    fig = plt.figure(figsize=(11,5))
    ax1 = fig.add_subplot(121, projection='3d')
    ax2 = fig.add_subplot(122)

    surf = ax1.plot_surface(X, Y, T, cmap='viridis')

    l1, = ax2.plot([], [], label="Actionneur")
    l2, = ax2.plot([], [], label="Centre")
    l3, = ax2.plot([], [], label="Sortie")

    ax2.set_xlim(0, sim_time)
    ax2.set_ylim(start_temp, start_temp + 5)
    ax2.set_xlabel("t [s]")
    ax2.set_ylabel("T [°C]")
    ax2.legend()

    time_sim = 0

    def step(T, Tn):
        Tn[1:-1,1:-1] = T[1:-1,1:-1] + alpha*dt*(
            (T[1:-1,2:] - 2*T[1:-1,1:-1] + T[1:-1,:-2]) / dx**2 +
            (T[2:,1:-1] - 2*T[1:-1,1:-1] + T[:-2,1:-1]) / dy**2)

        Tn[0:2, centre-1:centre+1] += Q_entree * dt / (rho * cp)
        Tn[1:-1,1:-1] -= (h*dt/(rho*cp*thickness))*(T[1:-1,1:-1]-T_amb)

        Tn[0,:]  = Tn[1,:]
        Tn[-1,:] = Tn[-2,:]
        Tn[:,0]  = Tn[:,1]
        Tn[:,-1] = Tn[:,-2]

        return Tn

    def update(frame):
        nonlocal T, Tn, time_sim, surf

        if not running:
            plt.close(fig)
            return

        for _ in range(steps_per_frame):
            if time_sim >= sim_time:
                break
            Tn = step(T, Tn)
            T, Tn = Tn, T
            time_sim += dt

        temps.append(time_sim)
        Tin.append(T[0, centre])
        Tmid.append(T[centre, centre])
        Tout.append(T[-1, centre])

        surf.remove()
        surf = ax1.plot_surface(X, Y, T, cmap='viridis')

        l1.set_data(temps, Tin)
        l2.set_data(temps, Tmid)
        l3.set_data(temps, Tout)

    ani = FuncAnimation(fig, update, interval=40)
    plt.show()

    data_out = data.copy()
    results_out = {"temps": temps, "Tin": Tin, "Tmid": Tmid, "Tout": Tout}

# ==========================
# Contrôles
# ==========================
def start():
    global running
    if not running:
        running = True
        data = {k: v.get() for k, v in params.items()}
        simulation(data)

def cancel():
    global running
    running = False

btn_frame = ttk.Frame(root)
btn_frame.pack(pady=20)

tk.Button(btn_frame, text="GO", width=15,
          bg="green", fg="white",
          command=start).pack(side="left", padx=10)

tk.Button(btn_frame, text="Cancel", width=15,
          bg="red", fg="white",
          command=cancel).pack(side="left", padx=10)

root.mainloop()

print(data_out)
print(results_out)
