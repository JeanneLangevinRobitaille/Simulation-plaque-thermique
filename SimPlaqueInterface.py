import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import json

#Fenêtre de l'interface
#==========================
root = tk.Tk()
root.title("Simulateur de plaque asservie en température")
root.geometry('1400x950')
running = False
paused = False

#Variables de sortie
#==========================
data_out = None
results_out = None

#Paramètres avec valeurs préfaites
#==========================
params = {
    "L_mm": tk.DoubleVar(value=117.5), #longueur
    "l_mm": tk.DoubleVar(value=61.5), #largeur
    "e_mm": tk.DoubleVar(value=1.7), #épaisseur
    "P_W": tk.DoubleVar(value=1.0),
    "t_s": tk.DoubleVar(value=150),
    "res": tk.DoubleVar(value=50),
    "Tamb_C": tk.DoubleVar(value=20),
    "alpha": tk.DoubleVar(value=97.0),
    "rho": tk.DoubleVar(value=2.7e-3),
    "Cp": tk.DoubleVar(value=0.9),
    "h": tk.DoubleVar(value=5.0e-5),
    "TEC_x_mm": tk.DoubleVar(value=0),
    "TEC_y_mm": tk.DoubleVar(value=5),
    "T1_x_mm": tk.DoubleVar(value=0),
    "T1_y_mm": tk.DoubleVar(value=14.57),
    "T2_x_mm": tk.DoubleVar(value=0),
    "T2_y_mm": tk.DoubleVar(value=59.42),
    "T3_x_mm": tk.DoubleVar(value=0),
    "T3_y_mm": tk.DoubleVar(value=103.79),
    "pert_x_mm": tk.DoubleVar(value=0),
    "pert_y_mm": tk.DoubleVar(value=38),
    "val_resistance": tk.DoubleVar(value=25.0),
    "tension_resistance": tk.DoubleVar(value=1.0),
    "frames_showed": tk.DoubleVar(value=1),
    "entry_filepath": tk.StringVar(value = ""),
    "output_filepath": tk.StringVar(value = "")
    }

#Fonctions affichage dans la fenêtre (modèles pour les titres)
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

#Structure principale de la fenêtre
#==========================
header_frame = ttk.Frame(root)
header_frame.pack(fill="x", pady=(15, 10))
main_frame = ttk.Frame(root)
main_frame.pack(fill="both", expand=True, padx=30)
main_frame.columnconfigure(0, weight=3)
main_frame.columnconfigure(1, weight=1)

#Colonne gauche
#==========================
left_frame = ttk.Frame(main_frame)
left_frame.grid(row=0, column=0, sticky="nw")

#Section pour les fichiers JSON
frame_geo = ttk.Frame(left_frame)
frame_geo.pack(anchor="w")
field(frame_geo, 0, "Ficher de sauvegarde", params["output_filepath"], '')

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
field(frame_sim, 4, "Saut d'image", params["frames_showed"], "image sautée")

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
ttk.Entry(frame_pert, textvariable=params["pert_x_mm"], 
          width=5).grid(row=0, column=1, padx=0)
ttk.Entry(frame_pert, textvariable=params["pert_y_mm"], 
          width=5).grid(row=0, column=2, padx=0)
ttk.Label(frame_pert, text="(x,y) mm").grid(row=0, column=3, padx=5)
ttk.Label(frame_pert, text="Résistance").grid(row=1, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["val_resistance"], 
          width=10).grid(row=1, column=1, columnspan=2)
ttk.Label(frame_pert, text="ohm").grid(row=1, column=3, padx=5)
ttk.Label(frame_pert, text="Tension").grid(row=2, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["tension_resistance"], 
          width=10).grid(row=2, column=1, columnspan=2)
ttk.Label(frame_pert, text="V").grid(row=2, column=3, padx=5)

#Simulation thermique
#==========================
def simulation(data):
    """Fonction principale qui fait la simulation thermique, 
    ce qui est appelé par FuncAnimation"""

    global running, paused, data_out, results_out

    #Espace de la plaque
    x = np.linspace(-data["l_mm"]/2, 
                    data["l_mm"]/2, int(data["res"])+1)
    y = np.linspace(0, data["L_mm"], int(data["res"])+1)
    X, Y = np.meshgrid(x, y)

    #Valeurs calculées simples
    dx = data["l_mm"] / (data["res"]-1)
    dy = data["L_mm"] / (data["res"]-1)
    dt = 0.2 * min(dx, dy)**2 / data["alpha"]
    dt = min(dt, 0.5/(data["alpha"]*((1/dx**2)+(1/dy**2))))
    volume_entree = (2*dx)*(2*dy)*data["e_mm"]
    Q_entree = (params["P_W"].get()) / volume_entree

    #Valeurs calculées thermiques
    cx = data["alpha"]*dt/dx**2
    cy = data["alpha"]*dt/dy**2
    conv_coeff = data["h"]*dt/(data["rho"]*data["Cp"]*data["e_mm"])
    
    #Valeurs initiales de l'espace de la plaque
    T = np.full_like(X, data["Tamb_C"], dtype=np.float32)
    Tn = T.copy()

    def xToKnot(x_coord):
        """Prend la coordonnée en x [mm] et donne une valeur approximative 
        de noeud sur la plaque"""
        return int(round((x_coord + data["l_mm"]/2) / dx))
        
    def yToKnot(y_coord):
        """Prend la coordonnée en y [mm] et donne une valeur approximative 
        de noeud sur la plaque"""
        return int(round(y_coord / dy))
    
    #Positions des différentes thermistances
    j1,i1 = xToKnot(data["T1_x_mm"]), yToKnot(data["T1_y_mm"])
    j2,i2 = xToKnot(data["T2_x_mm"]), yToKnot(data["T2_y_mm"])
    j3,i3 = xToKnot(data["T3_x_mm"]), yToKnot(data["T3_y_mm"])
    
    #Positions des différentes composantes
    j_tec, i_tec = xToKnot(data["TEC_x_mm"]), yToKnot(data["TEC_y_mm"])
    j_R, i_R = xToKnot(data["pert_x_mm"]), yToKnot(data["pert_y_mm"])

    def heatCalc(T, Tn, tec_coeff, res_coeff):
        """Le coeur de la simulation, la fonction qui fait le 
        calcul discret de la fonction de diffusion"""

        #Fonction de diffusion classique
        Tn[1:-1,1:-1] = T[1:-1,1:-1] + (
            cx*(T[1:-1,2:] - 2*T[1:-1,1:-1] + T[1:-1,:-2]) +
            cy*(T[2:,1:-1] - 2*T[1:-1,1:-1] + T[:-2,1:-1])
        )

        #Convection
        Tn[1:-1,1:-1] -= conv_coeff*(T[1:-1,1:-1] - data["Tamb_C"])

        #Ajout par les différents éléments
        Tn[i_tec:i_tec+2, j_tec-1:j_tec+1] += tec_coeff #le TEC
        Tn[i_R:i_R+2, j_R-1:j_R+1] += res_coeff #la résistance

        #Conditions limites pour la stabilité
        Tn[0,:] = Tn[1,:]
        Tn[-1,:] = Tn[-2,:]
        Tn[:,0] = Tn[:,1]
        Tn[:,-1] = Tn[:,-2]

        return Tn

    steps_per_frame = 150
    frame_count = 0
    temps, T1_vals, T2_vals, T3_vals = [], [], [], []
    
    #Positionnement des fenetres
    fig = plt.figure(figsize=(11,5))
    manager = plt.get_current_fig_manager()
    screen_width = manager.window.winfo_screenwidth()
    fig_width = 1100
    manager.window.wm_geometry(f"+{screen_width - fig_width}+50")

    time_sim = 0.0

    #Initialisation des graphiques
    #==========================
    surface_temperature = fig.add_subplot(121, projection='3d')
    surf = surface_temperature.plot_surface(
        X, Y, T,
        cmap='viridis',
        shade=False,
        rstride=2,
        cstride=2)
    surface_temperature.set_zlim(data["Tamb_C"], data["Tamb_C"] + 10)
    surface_temperature.set_xlabel("x [mm]")
    surface_temperature.set_ylabel("y [mm]")
    p1 = surface_temperature.scatter([], [], [], s=100, c="blue",
                                 edgecolors="black",
                                 depthshade=False,
                                 label='T1')
    p2 = surface_temperature.scatter([], [], [], s=100, c="orange",
                                    edgecolors="black",
                                    depthshade=False,
                                    label="T2")
    p3 = surface_temperature.scatter([], [], [], s=100, c="lime",
                                    edgecolors="black",
                                    depthshade=False,
                                    label="T3")
    surface_temperature.legend()
    ligne_temperature = fig.add_subplot(122)
    l_entree, = ligne_temperature.plot([], [], label="T1")
    l_centre, = ligne_temperature.plot([], [], label="T2")
    l_sortie, = ligne_temperature.plot([], [], label="T3")
    ligne_temperature.set_title(f"t = {time_sim}s")
    ligne_temperature.set_xlim(0, data["t_s"])
    ligne_temperature.set_ylim(data["Tamb_C"], data["Tamb_C"] + 5)
    ligne_temperature.set_xlabel("t [s]")
    ligne_temperature.set_ylabel("T [°C]")
    ligne_temperature.legend()

    def update(frame):
        """Fonction de mise à jour des graphiques et des listes d'informations"""

        nonlocal T, Tn, time_sim, surf, frame_count
        global paused

        if not running:
            plt.close(fig)
            return
        
        if paused:
            return
        
        # 🔥 Lire les valeurs en temps réel depuis l'interface
        current_P = params["P_W"].get()
        current_V = params["tension_resistance"].get()
        current_R = params["val_resistance"].get()

        # 🔥 Recalcul dynamique
        volume_entree = (2*dx)*(2*dy)*data["e_mm"]
        Q_entree = current_P / volume_entree

        tec_coeff = (Q_entree * dt) / (data["rho"] * data["Cp"])

        res_coeff = (current_V**2 * dt) / (
            current_R * data["rho"] * data["Cp"] * data["e_mm"] * dx * dy
        )

        for _ in range(steps_per_frame):
            if time_sim >= data["t_s"]:
                break
            Tn = heatCalc(T, Tn, tec_coeff, res_coeff)
            T, Tn = Tn, T
            time_sim += dt
        
        temps.append(time_sim)
        T1_vals.append(T[i1,j1])
        T2_vals.append(T[i2,j2])
        T3_vals.append(T[i3,j3])

        frame_count += 1
        if frame_count % data["frames_showed"] == 0:
            surf.remove()
            surf = surface_temperature.plot_surface(
                X, Y, T,
                cmap='viridis',
                shade=False,
                rstride=2,
                cstride=2)
            l_entree.set_data(temps, T1_vals)
            l_centre.set_data(temps, T2_vals)
            l_sortie.set_data(temps, T3_vals)
            p1._offsets3d = ([X[i1,j1]], [Y[i1,j1]], [T[i1,j1]])
            p2._offsets3d = ([X[i2,j2]], [Y[i2,j2]], [T[i2,j2]])
            p3._offsets3d = ([X[i3,j3]], [Y[i3,j3]], [T[i3,j3]])
            ligne_temperature.set_title(f"t = {time_sim:.2f} s")

    #Animation des choses, prend update() en entrée
    ani = FuncAnimation(fig, update, interval=40)
    plt.show()

    data_out = data.copy()
    results_out = {"temps": temps, "T1": T1_vals, "T2": T2_vals, "T3": T3_vals}

#Contrôle des fonctions de l'interface
#==========================
def start():
    global running
    if not running:
        running = True
        print("Simulation started")
        data = {k: v.get() for k, v in params.items()}
        simulation(data)

def pause():
    global paused
    paused = not paused
    print("Paused" if paused else "Resumed")

def save():
    global running
    print("Adding filepath for Save")
    filepath = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        title="Choisir où sauvegarder les résultats"
    )
    if filepath:
        params["output_filepath"].set(filepath)

def save_results():
    if results_out is None or data_out is None:
        print("Aucune donnée à sauvegarder")
        return
    filepath = params["output_filepath"].get()
    if not filepath:
        print("Aucun chemin sélectionné")
        return
    output = {
        "parametres": data_out,
        "resultats": results_out
    }
    with open(filepath, "w") as f:
        json.dump(
            output,
            f,
            indent=4,
            default=lambda x: x.item() if isinstance(x, np.generic) else x
        )
    print(f"Résultats sauvegardés dans {filepath}")
    
def input():
    print('Adding filepath for Input')
    filepath = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        title="Choisir un fichier de paramètres")
    if not filepath:
        print("Aucun fichier sélectionné")
        return
    params["entry_filepath"].set(filepath)
    with open(filepath, "r") as f:
        data = json.load(f)
    for key in params:
        if key in data:
            params[key].set(data[key])
        else:
            print(f"Clé manquante dans le JSON : {key}")
    print("Paramètres chargés avec succès")

def on_closing():
    global running
    running = False
    save_results()
    root.destroy()

#Boutons de l'interface
#==========================
frame_btn = ttk.Frame(root)
frame_btn.pack(pady=45)

tk.Button(frame_btn, text="GO", width=15,
          bg="green", fg="white",
          command=start).pack(side="left", padx=10)

tk.Button(frame_btn, text="Pause/Resume", width=15,
          bg="red", fg="white",
          command=pause).pack(side="left", padx=10)

tk.Button(frame_btn, text='Save', width=15,bg="blue", fg="white",
          command=save).pack(side="left", padx=10)

tk.Button(frame_btn, text='Input', width=15,bg="violet", fg="white",
          command=input).pack(side="left", padx=10)

tk.Button(frame_btn, text='Exit', width=15,bg="orange", fg="white",
          command=on_closing).pack(side="left", padx=10)

root.mainloop()