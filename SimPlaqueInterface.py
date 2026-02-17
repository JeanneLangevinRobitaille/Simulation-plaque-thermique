import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
from tkinter import ttk

#Fenetre de l'interface
#==========================
root = tk.Tk()
root.title("Simulateur de plaque asservie en température")
root.geometry('1000x1100')

running = False

# Variables de sortie
# ==========================
data_out = None
results_out = None

#Paramètres avec valeurs préfaites
#==========================
entry_filepath = ""
exit_filepath = ""
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
    "h": tk.DoubleVar(value=5e-5)}

#Affichage des sections
#==========================
def instructions(text):
    ttk.Label(root, text=text,
               font=("Arial", 11, "italic")).pack(anchor="n", pady=(10, 4))


def section_title(text):
    ttk.Label(root, text=text,
               font=("Arial", 11, "bold")).pack(anchor="w", pady=(10, 4))

def field(parent, row, label, var, unit):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(30, 10))
    ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=2)
    ttk.Label(parent, text=unit).grid(row=row, column=3, padx=5)

#Sections
#==========================
instructions("Appuyer sur Go pour activer la simulation")
instructions("Appuyer sur Cancel pour l'interrompre et/ou changer ses paramètres")
instructions("Fermer la fenêtre pour sauvegarder les données brutes de la simulation")
instructions("-"*950)

section_title("Chemin d'accès des fichiers")
frame_geo = ttk.Frame(root)
frame_geo.pack(anchor="w")

field(frame_geo, 0, "Ficher d'entrée", entry_filepath, '')
field(frame_geo, 1, "Ficher de sortie", exit_filepath, '')

section_title("Paramètres de la plaque")
frame_geo = ttk.Frame(root)
frame_geo.pack(anchor="w")

field(frame_geo, 0, "Longueur", params["L_mm"], "mm")
field(frame_geo, 1, "Largeur", params["l_mm"], "mm")
field(frame_geo, 2, "Épaisseur", params["e_mm"], "mm")

section_title("Paramètres de la simulation")
frame_sim = ttk.Frame(root)
frame_sim.pack(anchor="w")

field(frame_sim, 0, "Puissance entrée", params["P_W"], "W")
field(frame_sim, 1, "Temps de simulation", params["t_s"], "s")
field(frame_sim, 2, "Resolution", params["res"], "N x N")
field(frame_sim, 3, "Température initiale", params["T0_C"], "°C")
field(frame_sim, 4, "Température ambiante", params["Tamb_C"], "°C")

section_title("Paramètres physiques")
frame_adv = ttk.Frame(root)
frame_adv.pack(anchor="w")

field(frame_adv, 0, "α (diffusivité)", params["alpha"], "mm²/s")
field(frame_adv, 1, "ρ (densité)", params["rho"], "kg/mm³")
field(frame_adv, 2, "Cp", params["Cp"], "J/mg·K")
field(frame_adv, 3, "h (convection)", params["h"], "W/mm²·K")

#Simulation thermique
#==========================
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
    steps_per_frame = 250

    display_every = 10
    frame_count = 0

    volume_entree = (2*dx)*(2*dy)*thickness
    Q_entree = input_power / volume_entree

    temps, Tin, Tmid, Tout = [], [], [], []

    fig = plt.figure(figsize=(11,5))

    #Positionnement des fenetres
    manager = plt.get_current_fig_manager()
    screen_width = manager.window.winfo_screenwidth()
    fig_width = 1100
    manager.window.wm_geometry(f"+{screen_width - fig_width}+50")

    time_sim = 0.0

    surface_temperature = fig.add_subplot(121, projection='3d')
    surf = surface_temperature.plot_surface(X, Y, T, cmap='viridis')
    surface_temperature.set_zlim(start_temp,
                                 start_temp + (1 if input_power < 1 else 2))
    
    ligne_temperature = fig.add_subplot(122)
    l_entree, = ligne_temperature.plot([], [], label="Actionneur")
    l_centre, = ligne_temperature.plot([], [], label="Thermistance")
    l_sortie, = ligne_temperature.plot([], [], label="Point laser")

    ligne_temperature.set_xlim(0, sim_time)
    ligne_temperature.set_ylim(start_temp, 
                               start_temp + 5)
    ligne_temperature.set_xlabel("t [s]")
    ligne_temperature.set_ylabel("T [°C]")
    ligne_temperature.legend()

    def diapo(T, Tn):
        Tn[1:-1,1:-1] = T[1:-1,1:-1] + alpha*dt*(
            (T[1:-1,2:] - 2*T[1:-1,1:-1] + T[1:-1,:-2]) / dx**2 +
            (T[2:,1:-1] - 2*T[1:-1,1:-1] + T[:-2,1:-1]) / dy**2)

        Tn[0:2, centre-1:centre+1] += Q_entree * dt / (rho * cp)
        Tn[1:-1, 1:-1] -= (h*dt/(rho*cp*thickness))*(T[1:-1,1:-1]-T_amb)

        Tn[0,:]  = Tn[1,:]
        Tn[-1,:] = Tn[-2,:]
        Tn[:,0]  = Tn[:,1]
        Tn[:,-1] = Tn[:,-2]

        return Tn

    def update(frame):
        nonlocal T, Tn, time_sim, surf, frame_count

        if not running:
            plt.close(fig)
            return

        for _ in range(steps_per_frame):
            if time_sim >= sim_time:
                break
            Tn = diapo(T, Tn)
            T, Tn = Tn, T
            time_sim += dt

        temps.append(time_sim)
        Tin.append(T[0, centre])
        Tmid.append(T[centre, centre])
        Tout.append(T[-1, centre])

        frame_count += 1
        if frame_count % display_every == 0:
            surf.remove()
            surf = surface_temperature.plot_surface(X, Y, T, cmap='viridis')

        l_entree.set_data(temps, Tin)
        l_centre.set_data(temps, Tmid)
        l_sortie.set_data(temps, Tout)
        ligne_temperature.set_title(f"t = {time_sim:.2f} s")

    ani = FuncAnimation(fig, update, interval=40)
    plt.show()

    data_out = data.copy()
    results_out = {"temps": temps, "Tin": Tin, "Tmid": Tmid, "Tout": Tout}

#Controle
#==========================
def start():
    global running
    if not running:
        running = True
        data = {k: v.get() for k, v in params.items()}
        simulation(data)

def cancel():
    global running
    running = False

#Boutons
#==========================
frame_btn = ttk.Frame(root)
frame_btn.pack(pady=45)

tk.Button(frame_btn, text="GO", width=15,
          bg="green", fg="white",
          command=start).pack(side="left", padx=10)

tk.Button(frame_btn, text="Cancel", width=15,
          bg="red", fg="white",
          command=cancel).pack(side="left", padx=10)

root.mainloop()

print(data_out)
print(results_out)
