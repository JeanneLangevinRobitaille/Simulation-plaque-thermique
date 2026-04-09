import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
from tkinter import ttk
import pandas as pd
from scipy.optimize import minimize
import threading
from numba import njit
import os # Ajout pour forcer la fermeture

# ==========================================
# CONFIGURATION DES FICHIERS CSV
# ==========================================
fichiers_tests = [
    {"chemin": r"G:\Mon disque\University\H26\Design 2\Codes\Simulation\Perturbations\test puissance de 2.56 W (8V) à résist. perturbation.csv", "wattage": 2.56},
    {"chemin": r"G:\Mon disque\University\H26\Design 2\Codes\Simulation\Perturbations\test puissance perturbation à 4W et 10V.csv", "wattage": 4.0},
    {"chemin": r"G:\Mon disque\University\H26\Design 2\Codes\Simulation\Perturbations\mesure (puissance 0.81W et 4.5 V).csv", "wattage": 0.81},
    {"chemin": r"G:\Mon disque\University\H26\Design 2\Codes\Simulation\Perturbations\Mesures(3.24W et 9V).csv", "wattage": 3.24}
]

# ==========================================
# Fenêtre de l'interface
# ==========================================
root = tk.Tk()
root.title("Simulateur de plaque asservie en température")
root.geometry('1200x1100')
running = False

data_out = None
results_out = None

# Paramètres avec valeurs préfaites
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

# ==========================================
# Fonctions affichage UI
# ==========================================
def section_title(parent, text):
    ttk.Label(parent, text=text, font=("Arial", 11, "bold")).pack(anchor="w", pady=(10, 4))

def field(parent, row, label, var, unit):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(5, 10))
    ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=1)
    ttk.Label(parent, text=unit).grid(row=row, column=2, padx=5)

def coord_field(parent, row, label, varx, vary, unit):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(5, 10))
    ttk.Entry(parent, textvariable=varx, width=5).grid(row=row, column=1)
    ttk.Entry(parent, textvariable=vary, width=5).grid(row=row, column=2)
    ttk.Label(parent, text=unit).grid(row=row, column=3, padx=5)

header_frame = ttk.Frame(root)
header_frame.pack(fill="x", pady=(15, 10))
ttk.Label(header_frame, text="Appuyer sur Go pour activer la simulation", font=("Arial", 11, "italic")).pack()
ttk.Label(header_frame, text="Appuyer sur Cancel pour l'interrompre et/ou changer ses paramètres", font=("Arial", 11, "italic")).pack()
ttk.Label(header_frame, text="Appuyer sur Optimiser pour calibrer h, alpha et Cp selon les CSV", font=("Arial", 11, "bold")).pack()
ttk.Separator(root, orient="horizontal").pack(fill="x", pady=10)

main_frame = ttk.Frame(root)
main_frame.pack(fill="both", expand=True, padx=30)
main_frame.columnconfigure(0, weight=3)
main_frame.columnconfigure(1, weight=1)

left_frame = ttk.Frame(main_frame)
left_frame.grid(row=0, column=0, sticky="nw")

section_title(left_frame, "Chemin d'accès des fichiers")
frame_geo = ttk.Frame(left_frame)
frame_geo.pack(anchor="w")
field(frame_geo, 0, "Ficher d'entrée", params["entry_filepath"], '')
field(frame_geo, 1, "Ficher de sortie", params["output_filepath"], '')

section_title(left_frame, "Paramètres de la plaque")
frame_geo = ttk.Frame(left_frame)
frame_geo.pack(anchor="w")
field(frame_geo, 0, "Longueur", params["L_mm"], "mm")
field(frame_geo, 1, "Largeur", params["l_mm"], "mm")
field(frame_geo, 2, "Épaisseur", params["e_mm"], "mm")

section_title(left_frame, "Paramètres de la simulation")
frame_sim = ttk.Frame(left_frame)
frame_sim.pack(anchor="w")
field(frame_sim, 0, "Puissance entrée (Peltier)", params["P_W"], "W")
field(frame_sim, 1, "Temps simulation", params["t_s"], "s")
field(frame_sim, 2, "Résolution", params["res"], "N x N")
field(frame_sim, 3, "Température ambiante", params["Tamb_C"], "°C")
field(frame_sim, 4, "Saut d'image", params["frames_showed"], "image sautée")

section_title(left_frame, "Paramètres physiques")
frame_phys = ttk.Frame(left_frame)
frame_phys.pack(anchor="w")
field(frame_phys, 0, "α (diffusivité)", params["alpha"], "mm²/s")
field(frame_phys, 1, "ρ (densité)", params["rho"], "kg/mm³")
field(frame_phys, 2, "Cp (calorifique)", params["Cp"], "J/mg·K")
field(frame_phys, 3, "h (convection)", params["h"], "W/mm²·K")

right_frame = ttk.Frame(main_frame)
right_frame.grid(row=0, column=1, sticky="nw", padx=(40,0))

section_title(right_frame, "Coordonnées d'intérêt")
frame_coords = ttk.Frame(right_frame)
frame_coords.pack(anchor="w")
coord_field(frame_coords, 0, "TEC", params["TEC_x_mm"], params["TEC_y_mm"], "(x,y) mm")
coord_field(frame_coords, 1, "T1", params["T1_x_mm"], params["T1_y_mm"], "(x,y) mm")
coord_field(frame_coords, 2, "T2", params["T2_x_mm"], params["T2_y_mm"], "(x,y) mm")
coord_field(frame_coords, 3, "T3", params["T3_x_mm"], params["T3_y_mm"], "(x,y) mm")

section_title(right_frame, "Perturbation")
frame_pert = ttk.Frame(right_frame)
frame_pert.pack(anchor="w")
ttk.Label(frame_pert, text="Position").grid(row=0, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["pert_x_mm"], width=5).grid(row=0, column=1, padx=0)
ttk.Entry(frame_pert, textvariable=params["pert_y_mm"], width=5).grid(row=0, column=2, padx=0)
ttk.Label(frame_pert, text="(x,y) mm").grid(row=0, column=3, padx=5)
ttk.Label(frame_pert, text="Résistance").grid(row=1, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["val_resistance"], width=10).grid(row=1, column=1, columnspan=2)
ttk.Label(frame_pert, text="ohm").grid(row=1, column=3, padx=5)
ttk.Label(frame_pert, text="Tension").grid(row=2, column=0, sticky="w", padx=(5,10))
ttk.Entry(frame_pert, textvariable=params["tension_resistance"], width=10).grid(row=2, column=1, columnspan=2)
ttk.Label(frame_pert, text="V").grid(row=2, column=3, padx=5)

# ==========================================
# SIMULATION THERMIQUE (Visuelle UI)
# ==========================================
def simulation(data):
    global running, data_out, results_out

    x = np.linspace(-data["l_mm"]/2, data["l_mm"]/2, int(data["res"])+1)
    y = np.linspace(0, data["L_mm"], int(data["res"])+1)
    X, Y = np.meshgrid(x, y)

    dx = params["l_mm"].get() / (data["res"]-1)
    dy = params["L_mm"].get() / (data["res"]-1)
    dt = 0.2 * min(dx, dy)**2 / data["alpha"]
    dt = min(dt, 0.5/(data["alpha"]*((1/dx**2)+(1/dy**2))))
    volume_entree = (2*dx)*(2*dy)*data["e_mm"]
    Q_entree = (data["P_W"]) / volume_entree

    cx = data["alpha"]*dt/dx**2
    cy = data["alpha"]*dt/dy**2
    conv_coeff = data["h"]*dt/(data["rho"]*data["Cp"]*data["e_mm"])
    tec_coeff = (Q_entree*dt)/(data["rho"]*data["Cp"])
    res_coeff = (data["tension_resistance"]**2 * dt)/(data["val_resistance"]*data["rho"]*data["Cp"]*data["e_mm"]*dx*dy)

    T = np.full_like(X, data["Tamb_C"], dtype=np.float64)
    Tn = T.copy()

    def xToKnot(x_coord): return int(round((x_coord + data["l_mm"]/2) / dx))
    def yToKnot(y_coord): return int(round(y_coord / dy))
        
    j1,i1 = xToKnot(data["T1_x_mm"]), yToKnot(data["T1_y_mm"])
    j2,i2 = xToKnot(data["T2_x_mm"]), yToKnot(data["T2_y_mm"])
    j3,i3 = xToKnot(data["T3_x_mm"]), yToKnot(data["T3_y_mm"])
    j_tec, i_tec = xToKnot(data["TEC_x_mm"]), yToKnot(data["TEC_y_mm"])
    j_R, i_R = xToKnot(data["pert_x_mm"]), yToKnot(data["pert_y_mm"])

    def heatCalc(T, Tn):
        Tn[1:-1,1:-1] = T[1:-1,1:-1] + (
            cx*(T[1:-1,2:] - 2*T[1:-1,1:-1] + T[1:-1,:-2]) +
            cy*(T[2:,1:-1] - 2*T[1:-1,1:-1] + T[:-2,1:-1])
        )
        Tn[1:-1,1:-1] -= conv_coeff*(T[1:-1,1:-1] - data["Tamb_C"])
        Tn[i_tec:i_tec+2, j_tec-1:j_tec+1] += tec_coeff
        Tn[i_R:i_R+2, j_R-1:j_R+1] += res_coeff

        Tn[0,:] = Tn[1,:]
        Tn[-1,:] = Tn[-2,:]
        Tn[:,0] = Tn[:,1]
        Tn[:,-1] = Tn[:,-2]
        return Tn

    steps_per_frame = 150
    frame_count = 0
    temps, T1_vals, T2_vals, T3_vals = [], [], [], []
    
    fig = plt.figure(figsize=(11,5))
    manager = plt.get_current_fig_manager()
    screen_width = manager.window.winfo_screenwidth()
    fig_width = 1100
    manager.window.wm_geometry(f"+{screen_width - fig_width}+50")

    time_sim = 0.0

    surface_temperature = fig.add_subplot(121, projection='3d')
    surf = surface_temperature.plot_surface(X, Y, T, cmap='viridis', shade=False, rstride=2, cstride=2)
    surface_temperature.set_zlim(data["Tamb_C"], data["Tamb_C"] + 10)
    surface_temperature.set_xlabel("x [mm]")
    surface_temperature.set_ylabel("y [mm]")
    p1 = surface_temperature.scatter([], [], [], s=100, c="blue", edgecolors="black", depthshade=False, label='T1')
    p2 = surface_temperature.scatter([], [], [], s=100, c="orange", edgecolors="black", depthshade=False, label="T2")
    p3 = surface_temperature.scatter([], [], [], s=100, c="lime", edgecolors="black", depthshade=False, label="T3")
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
        nonlocal T, Tn, time_sim, surf, frame_count
        if not running:
            plt.close(fig)
            return
        for _ in range(steps_per_frame):
            if time_sim >= data["t_s"]: break
            Tn = heatCalc(T, Tn)
            T, Tn = Tn, T
            time_sim += dt
        
        temps.append(time_sim)
        T1_vals.append(T[i1,j1])
        T2_vals.append(T[i2,j2])
        T3_vals.append(T[i3,j3])

        frame_count += 1
        if frame_count % data["frames_showed"] == 0:
            surf.remove()
            surf = surface_temperature.plot_surface(X, Y, T, cmap='viridis', shade=False, rstride=2, cstride=2)
            l_entree.set_data(temps, T1_vals)
            l_centre.set_data(temps, T2_vals)
            l_sortie.set_data(temps, T3_vals)
            p1._offsets3d = ([X[i1,j1]], [Y[i1,j1]], [T[i1,j1]])
            p2._offsets3d = ([X[i2,j2]], [Y[i2,j2]], [T[i2,j2]])
            p3._offsets3d = ([X[i3,j3]], [Y[i3,j3]], [T[i3,j3]])
            ligne_temperature.set_title(f"t = {time_sim:.2f} s")

    ani = FuncAnimation(fig, update, interval=40)
    plt.show()

    data_out = data.copy()
    results_out = {"temps": temps, "T1": T1_vals, "T2": T2_vals, "T3": T3_vals}


# ==========================================
# MODULE D'OPTIMISATION (Headless TURBO NUMBA)
# ==========================================
@njit
def fast_heat_loop(T, Tn, cx, cy, conv_coeff, res_coeff, Tamb_C, i_R, j_R, dt, t_max, i1, j1, i2, j2, i3, j3):
    max_steps = int(t_max / dt) + 5 
    temps_sim = np.zeros(max_steps)
    T1_sim = np.zeros(max_steps)
    T2_sim = np.zeros(max_steps)
    T3_sim = np.zeros(max_steps)
    
    time_sim = 0.0
    step = 0
    
    while time_sim <= t_max:
        Tn[1:-1,1:-1] = T[1:-1,1:-1] + (
            cx*(T[1:-1,2:] - 2*T[1:-1,1:-1] + T[1:-1,:-2]) +
            cy*(T[2:,1:-1] - 2*T[1:-1,1:-1] + T[:-2,1:-1])
        )
        Tn[1:-1,1:-1] -= conv_coeff*(T[1:-1,1:-1] - Tamb_C)
        Tn[i_R:i_R+2, j_R-1:j_R+1] += res_coeff

        Tn[0,:] = Tn[1,:]
        Tn[-1,:] = Tn[-2,:]
        Tn[:,0] = Tn[:,1]
        Tn[:,-1] = Tn[:,-2]

        T[:] = Tn[:]
        time_sim += dt
        
        temps_sim[step] = time_sim
        T1_sim[step] = T[i1, j1]
        T2_sim[step] = T[i2, j2]
        T3_sim[step] = T[i3, j3]
        step += 1

    return temps_sim[:step], T1_sim[:step], T2_sim[:step], T3_sim[:step]

def run_simulation_headless(alpha, h, Cp, rho, data, t_max):
    dx = data["l_mm"] / (data["res"] - 1)
    dy = data["L_mm"] / (data["res"] - 1)
    dt = 0.2 * min(dx, dy)**2 / alpha
    dt = min(dt, 0.5 / (alpha * ((1/dx**2) + (1/dy**2))))
    
    cx = alpha * dt / dx**2
    cy = alpha * dt / dy**2
    conv_coeff = h * dt / (rho * Cp * data["e_mm"])
    res_coeff = (data["tension_resistance"]**2 * dt) / (data["val_resistance"] * rho * Cp * data["e_mm"] * dx * dy)
    
    Ny = int(data["res"]) + 1
    Nx = int(data["res"]) + 1
    T = np.full((Ny, Nx), data["Tamb_C"], dtype=np.float64)
    Tn = T.copy()

    def xToKnot(x_coord): return int(round((x_coord + data["l_mm"]/2) / dx))
    def yToKnot(y_coord): return int(round(y_coord / dy))
    
    j1, i1 = xToKnot(data["T1_x_mm"]), yToKnot(data["T1_y_mm"])
    j2, i2 = xToKnot(data["T2_x_mm"]), yToKnot(data["T2_y_mm"])
    j3, i3 = xToKnot(data["T3_x_mm"]), yToKnot(data["T3_y_mm"])
    j_R, i_R = xToKnot(data["pert_x_mm"]), yToKnot(data["pert_y_mm"])

    return fast_heat_loop(T, Tn, cx, cy, conv_coeff, res_coeff, data["Tamb_C"], i_R, j_R, dt, t_max, i1, j1, i2, j2, i3, j3)

def optimiser_en_arriere_plan():
    print("\n--- DÉBUT DE L'OPTIMISATION FINE (MODE TURBO) ---")
    data_base = {k: v.get() for k, v in params.items()}
    
    data_base["res"] = 20.0 
    data_base["rho"] = 2.7e-3 
    
    base_alpha = data_base["alpha"]
    base_h = data_base["h"]
    base_Cp = data_base["Cp"]

    donnees_experiences = []
    try:
        for test in fichiers_tests:
            df = pd.read_csv(test["chemin"])
            temps_brut = df['Temps_s'].values
            temps_zero = temps_brut - temps_brut[0] 
            
            donnees_experiences.append({
                "wattage": test["wattage"],
                "t_exp": temps_zero,
                "T1_exp": df['T1'].values,
                "T2_exp": df['T2'].values,
                "T3_exp": df['T3'].values
            })
    except Exception as e:
        print(f"Erreur lors du chargement des CSV. Avez-vous mis les bons chemins ? ({e})")
        return

    nombre_total_points = sum(len(exp["t_exp"]) * 3 for exp in donnees_experiences)

    def objective_function(k_factors):
        k_alpha, k_h, k_Cp = k_factors
        
        alpha_test = base_alpha * k_alpha
        h_test = base_h * k_h
        Cp_test = base_Cp * k_Cp
        rho_fixe = data_base["rho"]
        
        erreur_globale_totale = 0.0
        
        for exp in donnees_experiences:
            tension_calculee = np.sqrt(exp["wattage"] * data_base["val_resistance"])
            data_base["tension_resistance"] = tension_calculee
            
            t_max = exp["t_exp"][-1]
            
            t_sim, T1_s, T2_s, T3_s = run_simulation_headless(alpha_test, h_test, Cp_test, rho_fixe, data_base, t_max)
            
            T1_interp = np.interp(exp["t_exp"], t_sim, T1_s)
            T2_interp = np.interp(exp["t_exp"], t_sim, T2_s)
            T3_interp = np.interp(exp["t_exp"], t_sim, T3_s)
            
            erreur_exp = np.sum((T1_interp - exp["T1_exp"])**2) + \
                         np.sum((T2_interp - exp["T2_exp"])**2) + \
                         np.sum((T3_interp - exp["T3_exp"])**2)
            erreur_globale_totale += erreur_exp
            
        erreur_moyenne_degres = np.sqrt(erreur_globale_totale / nombre_total_points)
        print(f"Test -> a:{k_alpha:.4f}, h:{k_h:.4f}, Cp:{k_Cp:.4f} | Erreur: {erreur_moyenne_degres:.4f} °C")
        return erreur_globale_totale

    guess_initial = [1.0, 1.0, 1.0]
    bornes = ((0.5, 2.0), (0.01, 50.0), (0.5, 2.0))
    
    resultat = minimize(
        objective_function, 
        guess_initial, 
        bounds=bornes, 
        method='L-BFGS-B', 
        options={'disp': False, 'ftol': 1e-5, 'eps': 1e-3}
    )
    
    if resultat.success:
        k_a, k_h, k_Cp = resultat.x
        nouveau_alpha = base_alpha * k_a
        nouveau_h = base_h * k_h
        nouveau_Cp = base_Cp * k_Cp
        
        print("\n=== SUCCÈS DE L'OPTIMISATION ===")
        print(f"Nouveau Alpha : {nouveau_alpha:.2f}")
        print(f"Nouveau h     : {nouveau_h:.3e}")
        print(f"Nouveau Cp    : {nouveau_Cp:.3f}")
        
        # Mise à jour de l'interface graphique
        params["alpha"].set(round(nouveau_alpha, 2))
        params["h"].set(round(nouveau_h, 7))
        params["Cp"].set(round(nouveau_Cp, 3))
        
        # --- BLOC DE SAUVEGARDE POUR NE PAS PERDRE LES VARIABLES ---
        texte_sauvegarde = f"""
    "alpha": tk.DoubleVar(value={nouveau_alpha:.2f}),
    "h": tk.DoubleVar(value={nouveau_h:.3e}),
    "Cp": tk.DoubleVar(value={nouveau_Cp:.3f}),
    "rho": tk.DoubleVar(value={data_base['rho']:.4e}),
        """
        
        print("\n==================================================================")
        print("🎉 REMPLACEZ CES LIGNES DANS VOTRE DICTIONNAIRE 'params' EN HAUT 🎉")
        print("==================================================================")
        print(texte_sauvegarde)
        print("==================================================================")
        
        # Sauvegarde également dans un fichier texte physique dans le dossier courant
        with open("parametres_optimises.txt", "w") as f:
            f.write("Valeurs optimisées à copier-coller dans votre code source :\n")
            f.write(texte_sauvegarde)
            
    else:
        print("\nÉchec de l'optimisation :", resultat.message)

# ==========================================
# Contrôle
# ==========================================
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

def start_optimization():
    print("Lancement du thread d'optimisation. Regardez la console !")
    # L'ajout de daemon=True fait en sorte que ce thread meurt si on ferme l'application
    threading.Thread(target=optimiser_en_arriere_plan, daemon=True).start()

# --- NOUVEAU : Fonction de fermeture propre (Tuer le processus) ---
def on_closing():
    print("\nFermeture forcée de l'application (Kill)...")
    root.quit()
    os._exit(0) # Tueur de processus zombie (Arrête tout instantanément)

root.protocol("WM_DELETE_WINDOW", on_closing) # Intercepte le clic sur le X
# ------------------------------------------------------------------
    
# ==========================================
# Boutons
# ==========================================
frame_btn = ttk.Frame(root)
frame_btn.pack(pady=45)

tk.Button(frame_btn, text="GO", width=15, bg="green", fg="white", command=start).pack(side="left", padx=10)
tk.Button(frame_btn, text="Cancel", width=15, bg="red", fg="white", command=cancel).pack(side="left", padx=10)
tk.Button(frame_btn, text="Optimiser", width=20, bg="blue", fg="white", command=start_optimization).pack(side="left", padx=10)

root.mainloop()

if (path := params["entry_filepath"].get()):
    print(path)

print(data_out)
print(results_out)