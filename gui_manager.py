import tkinter as tk

class FinestraDisegno:
    def __init__(self, coda_punti, coda_telemetria, larghezza=500, altezza=500):
        self.coda_punti = coda_punti
        self.coda_telemetria = coda_telemetria
        
        self.root = tk.Tk()
        self.root.title("Pannello di Controllo e Disegno")
        
        # --- FRAME SINISTRO: Telemetria ---
        self.frame_sinistro = tk.Frame(self.root, bg="#f0f0f0", padx=20, pady=20)
        self.frame_sinistro.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(self.frame_sinistro, text="DATI TELEMETRIA", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(anchor=tk.NW, pady=(0, 10))
        
        # Etichetta che conterrà i valori aggiornati
        self.label_telemetria = tk.Label(self.frame_sinistro, text="In attesa dei dati...", font=("Courier", 10), bg="#f0f0f0", justify=tk.LEFT)
        self.label_telemetria.pack(anchor=tk.NW)
        
        # --- FRAME DESTRO: Foglio da disegno ---
        self.frame_destro = tk.Frame(self.root, bg="gray", padx=10, pady=10)
        self.frame_destro.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        self.canvas = tk.Canvas(self.frame_destro, width=larghezza, height=altezza, bg="white")
        self.canvas.pack()
        
        # Avvia il loop di aggiornamento dell'interfaccia
        self.aggiorna_interfaccia()

    def aggiorna_interfaccia(self):
        # 1. Aggiorna il disegno se ci sono nuovi punti
        while not self.coda_punti.empty():
            punto = self.coda_punti.get()
            x, y = punto[0], punto[1]
            raggio = 1
            self.canvas.create_oval(x - raggio, y - raggio, x + raggio, y + raggio, fill="black", outline="black")
            
        # 2. Aggiorna il testo della telemetria se ci sono nuovi dati
        while not self.coda_telemetria.empty():
            dati = self.coda_telemetria.get()
            # Formattiamo i dati ricevuti (adattalo a come preferisci visualizzarli)
            testo_formattato = f"Queue Level : {dati[0]}\nValore 2    : {dati[1]}\nValore 3    : {dati[2]}\nValore 4    : {dati[3]}"
            self.label_telemetria.config(text=testo_formattato)
        
        # Richiama questa funzione ogni 50 millisecondi
        self.root.after(50, self.aggiorna_interfaccia)

    def avvia(self):
        self.root.mainloop()