import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
from tkinter import ttk

#Fenetre de l'interface
#==========================
root = tk.Tk()
root.title("Simulateur de plaque asservie en température")
root.geometry('1200x1100')
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
    "Tamb_C": tk.DoubleVar(value=20),
    "alpha": tk.DoubleVar(value=97),
    "rho": tk.DoubleVar(value=2.7e-3),
    "Cp": tk.DoubleVar(value=0.9),
    "h": tk.DoubleVar(value=5e-5),
    "TEC_x_mm": tk.DoubleVar(value=0),
    "TEC_y_mm": tk.DoubleVar(value=0),
    "T1_x_mm": tk.DoubleVar(value=0),
    "T1_y_mm": tk.DoubleVar(value=0),
    "T2_x_mm": tk.DoubleVar(value=0),
    "T2_y_mm": tk.DoubleVar(value=0),
    "T3_x_mm": tk.DoubleVar(value=0),
    "T3_y_mm": tk.DoubleVar(value=0),
    "pert_x_mm": tk.DoubleVar(value=0),
    "pert_y_mm": tk.DoubleVar(value=0),
    "val_Resistance": tk.DoubleVar(value=0.0),
    "tension_resistance": tk.DoubleVar(value=0.0),
    "sim_speed": tk.DoubleVar(value=1)
    }

#Fonctions affichage
    #==========================
def section_title(parent, text):
    ttk.Label(parent, text=text,
            font=("Arial", 11, "bold")).pack(anchor="w", pady=(10, 4))

def field(parent, row, label, var, unit):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(5, 10))
    ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=1)
    ttk.Label(parent, text=unit).grid(row=row, column=2, padx=5)

def coord_field(parent, row, label, varx, vary, unit):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(5, 10))
    ttk.Entry(parent, textvariable=varx, width=5).grid(row=row, column=1)
    ttk.Entry(parent, textvariable=vary, width=5).grid(row=row, column=2)
    ttk.Label(parent, text=unit).grid(row=row, column=3, padx=5)

#Texte d'instruction
#==========================
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

#Structure principale
#==========================
main_frame = ttk.Frame(root)
main_frame.pack(fill="both", expand=True, padx=30)
main_frame.columnconfigure(0, weight=3)
main_frame.columnconfigure(1, weight=1)

#Colonne gauche
#==========================
left_frame = ttk.Frame(main_frame)
left_frame.grid(row=0, column=0, sticky="nw")

#Section pour les fichiers JSON
section_title(left_frame, "Chemin d'accès des fichiers")
frame_geo = ttk.Frame(left_frame)
frame_geo.pack(anchor="w")

field(frame_geo, 0, "Ficher d'entrée", entry_filepath, '')
field(frame_geo, 1, "Ficher de sortie", exit_filepath, '')

#Section paramètres de la plaque
section_title(left_frame, "Paramètres de la plaque")
frame_geo = ttk.Frame(left_frame)
frame_geo.pack(anchor="w")
field(frame_geo, 0, "Longueur", params["L_mm"], "mm")
field(frame_geo, 1, "Largeur", params["l_mm"], "mm")
field(frame_geo, 2, "Épaisseur", params["e_mm"], "mm")

#Section paramètres de la simulation
section_title(left_frame, "Paramètres de la simulation")
frame_sim = ttk.Frame(left_frame)
frame_sim.pack(anchor="w")
field(frame_sim, 0, "Puissance entrée", params["P_W"], "W")
field(frame_sim, 1, "Temps simulation", params["t_s"], "s")
field(frame_sim, 2, "Résolution", params["res"], "N x N")
field(frame_sim, 3, "Température ambiante", params["Tamb_C"], "°C")
field(frame_sim, 4, "Rapidité de la simulation", params["sim_speed"], "multiplicateur")

#Section paramètres physiques
section_title(left_frame, "Paramètres physiques")
frame_phys = ttk.Frame(left_frame)
frame_phys.pack(anchor="w")
field(frame_phys, 0, "α (diffusivité)", params["alpha"], "mm²/s")
field(frame_phys, 1, "ρ (densité)", params["rho"], "kg/mm³")
field(frame_phys, 2, "Cp (calorifique massique)", params["Cp"], "J/mg·K")
field(frame_phys, 3, "h (convection)", params["h"], "W/mm²·K")

#Colonne droite
#==========================
right_frame = ttk.Frame(main_frame)
right_frame.grid(row=0, column=1, sticky="nw", padx=(40,0))

#Section coordonnées d'intérêt
section_title(right_frame, "Coordonnées d'intérêt")
frame_coords = ttk.Frame(right_frame)
frame_coords.pack(anchor="w")
coord_field(frame_coords, 0, "TEC", params["TEC_x_mm"], params["TEC_y_mm"], "(x,y) mm")
coord_field(frame_coords, 1, "T1", params["T1_x_mm"], params["T1_y_mm"], "(x,y) mm")
coord_field(frame_coords, 2, "T2", params["T2_x_mm"], params["T2_y_mm"], "(x,y) mm")
coord_field(frame_coords, 3, "T3", params["T3_x_mm"], params["T3_y_mm"], "(x,y) mm")

#Section perturbation
section_title(right_frame, "Perturbation")
frame_pert = ttk.Frame(right_frame)
frame_pert.pack(anchor="w")
ttk.Label(frame_pert, text="Position").grid(row=0, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["pert_x_mm"], width=5).grid(row=0, column=1, padx=0)
ttk.Entry(frame_pert, textvariable=params["pert_y_mm"], width=5).grid(row=0, column=2, padx=0)
ttk.Label(frame_pert, text="(x,y) mm").grid(row=0, column=3, padx=5)
ttk.Label(frame_pert, text="Résistance").grid(row=1, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["val_Resistance"], width=10).grid(row=1, column=1, columnspan=2)
ttk.Label(frame_pert, text="ohm").grid(row=1, column=3, padx=5)
ttk.Label(frame_pert, text="Tension").grid(row=2, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["tension_resistance"], width=10).grid(row=2, column=1, columnspan=2)
ttk.Label(frame_pert, text="V").grid(row=2, column=3, padx=5)

#Simulation thermique
#==========================
def simulation(data):
    global running, data_out, results_out

    input_power = data["P_W"]
    start_temp = data["Tamb_C"]
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
    V = data["tension_resistance"]

    x = np.linspace(-width/2, width/2, resolution+1)
    y = np.linspace(0, length, resolution+1)
    X, Y = np.meshgrid(x, y)

    T = np.full_like(X, start_temp, dtype=float)
    Tn = T.copy()

    dx = width / resolution
    dy = length / resolution
    centre = resolution // 2

    def coordToKnotX(x):
        pass

    def coordToKnotY(y):
        pass

    dt = 0.2 * min(dx, dy)**2 / alpha
    steps_per_frame = 150

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
    ligne_temperature.set_title(f"t = {time_sim}s")
    ligne_temperature.set_xlim(0, sim_time)
    ligne_temperature.set_ylim(start_temp, 
                               start_temp + 5)
    ligne_temperature.set_xlabel("t [s]")
    ligne_temperature.set_ylabel("T [°C]")
    ligne_temperature.legend()

    def update(frame):
        nonlocal T, Tn, time_sim, surf, frame_count

        if not running:
            plt.close(fig)
            return

        def diapo(T, Tn):
            #Équation de diffusion thermique
            Tn[1:-1,1:-1] = T[1:-1,1:-1] + alpha*dt*(
                    (T[1:-1,2:] - 2*T[1:-1,1:-1] + T[1:-1,:-2]) / dx**2 +
                    (T[2:,1:-1] - 2*T[1:-1,1:-1] + T[:-2,1:-1]) / dy**2)

            #Chaleur ajoutée par le TEC
            Tn[0:2, centre-1:centre+1] += (Q_entree*dt
                    /(rho * cp))

            #Effet Joule de la résistance
            

            #Effet de la convection
            Tn[1:-1, 1:-1] -= (h*dt/(rho*
                    cp*thickness))*(T[1:-1,1:-1]-T_amb)

            #Conditions aux limites
            Tn[0,:]  = Tn[1,:]
            Tn[-1,:] = Tn[-2,:]
            Tn[:,0]  = Tn[:,1]
            Tn[:,-1] = Tn[:,-2]

            return Tn

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
        if frame_count % data["sim_speed"] == 0:
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
        print("Simulation started")
        data = {k: v.get() for k, v in params.items()}
        simulation(data)

def cancel():
    global running
    print("Simulation canceled")
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
