import tkinter as tk
from tkinter import ttk, colorchooser, filedialog
from PIL import Image, ImageDraw, ImageFont
import qrcode
import vobject
import os
import glob

def create_vcard(name, title, company, phone, email):
    # Create vCard // Crée une vCard
    vcard = vobject.vCard()
    vcard.add('fn').value = name
    vcard.add('n').value = vobject.vcard.Name(family=name.split()[-1], given=name.split()[0])
    vcard.add('org').value = [company]
    vcard.add('title').value = title
    vcard.add('tel').value = phone
    vcard.add('email').value = email
    return vcard.serialize()

def generate_qr_code(data, size=300):
    # Generate QR code // Génère un code QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img

def draw_text(draw, position, text, font, color, center=True):
    # Draw text on the image // Dessine du texte sur l'image
    if center:
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        position = (position[0] - text_width // 2, position[1])
    draw.text(position, text, font=font, fill=color)

def create_business_card(width, height, name, title, company, phone, email, font_path, font_sizes, name_color, title_color, company_color, background_color, background_image_path, output_path):
    # Create a blank image with background color // Crée une image vierge avec une couleur de fond
    base = Image.new('RGBA', (width, height), background_color if background_color else (173, 216, 230))
    
    border_color = (0, 0, 0)
    border_width = 10
    draw = ImageDraw.Draw(base)
    draw.rectangle([border_width // 2, border_width // 2, width - border_width // 2, height - border_width // 2], outline=border_color, width=border_width)
    
    if background_image_path:
        # Load and resize background image while maintaining aspect ratio // Charge et redimensionne l'image de fond en conservant le ratio
        bg_image = Image.open(background_image_path).convert("RGBA")
        bg_image_ratio = bg_image.width / bg_image.height
        target_height = height // 3
        target_width = int(target_height * bg_image_ratio)
        
        if target_width > width:
            target_width = width
            target_height = int(target_width / bg_image_ratio)
        
        bg_image = bg_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        base.paste(bg_image, ((width - target_width) // 2, height - target_height - border_width), bg_image)
    
    # Generate vCard data and QR code // Génère les données vCard et le code QR
    vcard_data = create_vcard(name, title, company, phone, email)
    qr_img = generate_qr_code(vcard_data, size=300)
    
    # Calculate positions for QR code and texts // Calcule les positions pour le code QR et les textes
    margin = 50
    qr_position = ((width - qr_img.width) // 2, height // 4 - qr_img.height // 2)
    text_y_start = qr_position[1] + qr_img.height + margin
    text_positions = {
        'name': (width // 2, text_y_start),
        'title': (width // 2, text_y_start + 60),
        'company': (width // 2, text_y_start + 120)
    }
    
    # Paste QR code // Colle le code QR
    base.paste(qr_img, qr_position, qr_img)
    
    # Load fonts and draw texts // Charge les polices et dessine les textes
    name_font = ImageFont.truetype(font_path, font_sizes['name'])
    title_font = ImageFont.truetype(font_path, font_sizes['title'])
    company_font = ImageFont.truetype(font_path, font_sizes['company'])
    
    draw_text(draw, text_positions['name'], name, name_font, name_color)
    draw_text(draw, text_positions['title'], title, title_font, title_color)
    draw_text(draw, text_positions['company'], company, company_font, company_color)
    
    # Draw separating line // Dessine une ligne de séparation
    line_y = qr_position[1] + qr_img.height + margin // 4
    draw.line([(margin, line_y), (width - margin, line_y)], fill=border_color, width=2)
    
    # Save the business card // Sauvegarde la carte de visite
    base.save(output_path)
    print(f'Business card saved to {output_path}')
    return base

def select_color():
    # Open color chooser // Ouvre le sélecteur de couleur
    color_code = colorchooser.askcolor(title="Choose color")
    return color_code[1] if color_code[1] else "#ADD8E6"

def select_background_image():
    # Open file dialog to select background image // Ouvre la boîte de dialogue pour sélectionner une image de fond
    image_path = filedialog.askopenfilename(title="Select Background Image", filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
    return image_path

def preview_card():
    # Preview the business card // Prévisualise la carte de visite
    name = name_entry.get()
    title = title_entry.get()
    company = company_entry.get()
    phone = phone_entry.get()
    email = email_entry.get()
    font_path = font_dict[font_var.get()]
    font_sizes = {
        'name': int(name_font_size_var.get()),
        'title': int(title_font_size_var.get()),
        'company': int(company_font_size_var.get())
    }
    name_color = name_color_var.get()
    title_color = title_color_var.get()
    company_color = company_color_var.get()
    bg_color = bg_color_var.get()
    bg_image_path = bg_image_path_var.get()
    
    preview_image = create_business_card(600, 900, name, title, company, phone, email, font_path, font_sizes, name_color, title_color, company_color, bg_color, bg_image_path, "preview.png")
    preview_image.show()

def save_card():
    # Save the business card // Sauvegarde la carte de visite
    name = name_entry.get()
    title = title_entry.get()
    company = company_entry.get()
    phone = phone_entry.get()
    email = email_entry.get()
    font_path = font_dict[font_var.get()]
    font_sizes = {
        'name': int(name_font_size_var.get()),
        'title': int(title_font_size_var.get()),
        'company': int(company_font_size_var.get())
    }
    name_color = name_color_var.get()
    title_color = title_color_var.get()
    company_color = company_color_var.get()
    bg_color = bg_color_var.get()
    bg_image_path = bg_image_path_var.get()
    
    save_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
    if save_path:
        create_business_card(600, 900, name, title, company, phone, email, font_path, font_sizes, name_color, title_color, company_color, bg_color, bg_image_path, save_path)

def get_system_fonts():
    # Get system fonts // Récupère les polices système
    if os.name == 'nt':  # Windows
        font_dir = os.path.join(os.environ['WINDIR'], 'Fonts')
        fonts = glob.glob(font_dir + "/*.ttf") + glob.glob(font_dir + "/*.TTF")
    elif os.name == 'posix':  # macOS and Linux
        font_dirs = ['/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.fonts')]
        fonts = []
        for font_dir in font_dirs:
            fonts += glob.glob(font_dir + "/*.ttf") + glob.glob(font_dir + "/*.TTF")
    font_names = [os.path.basename(font) for font in fonts]
    font_dict = {name: path for name, path in zip(font_names, fonts)}
    return font_dict

# Create the main window // Crée la fenêtre principale
root = tk.Tk()
root.title("Business Card Generator")

# User details input // Saisie des détails de l'utilisateur
tk.Label(root, text="Name").grid(row=0, column=0, padx=10, pady=5)
name_entry = tk.Entry(root)
name_entry.grid(row=0, column=1, padx=10, pady=5)

tk.Label(root, text="Title").grid(row=1, column=0, padx=10, pady=5)
title_entry = tk.Entry(root)
title_entry.grid(row=1, column=1, padx=10, pady=5)

tk.Label(root, text="Company").grid(row=2, column=0, padx=10, pady=5)
company_entry = tk.Entry(root)
company_entry.grid(row=2, column=1, padx=10, pady=5)

tk.Label(root, text="Phone").grid(row=3, column=0, padx=10, pady=5)
phone_entry = tk.Entry(root)
phone_entry.grid(row=3, column=1, padx=10, pady=5)

tk.Label(root, text="Email").grid(row=4, column=0, padx=10, pady=5)
email_entry = tk.Entry(root)
email_entry.grid(row=4, column=1, padx=10, pady=5)

# Font selection // Sélection de la police
tk.Label(root, text="Font").grid(row=5, column=0, padx=10, pady=5)
font_dict = get_system_fonts()
font_var = tk.StringVar()
font_combobox = ttk.Combobox(root, textvariable=font_var, values=list(font_dict.keys()), state='readonly')
font_combobox.grid(row=5, column=1, padx=10, pady=5)
font_combobox.current(0)  # Set the first font as the default // Définit la première police comme police par défaut

# Font size selection for name // Sélection de la taille de la police pour le nom
tk.Label(root, text="Name Font Size").grid(row=6, column=0, padx=10, pady=5)
name_font_size_var = tk.StringVar(value="40")
name_font_size_combobox = ttk.Combobox(root, textvariable=name_font_size_var, values=[str(i) for i in range(10, 101, 2)], state='readonly')
name_font_size_combobox.grid(row=6, column=1, padx=10, pady=5)

# Font size selection for title // Sélection de la taille de la police pour le titre
tk.Label(root, text="Title Font Size").grid(row=7, column=0, padx=10, pady=5)
title_font_size_var = tk.StringVar(value="40")
title_font_size_combobox = ttk.Combobox(root, textvariable=title_font_size_var, values=[str(i) for i in range(10, 101, 2)], state='readonly')
title_font_size_combobox.grid(row=7, column=1, padx=10, pady=5)

# Font size selection for company // Sélection de la taille de la police pour l'entreprise
tk.Label(root, text="Company Font Size").grid(row=8, column=0, padx=10, pady=5)
company_font_size_var = tk.StringVar(value="40")
company_font_size_combobox = ttk.Combobox(root, textvariable=company_font_size_var, values=[str(i) for i in range(10, 101, 2)], state='readonly')
company_font_size_combobox.grid(row=8, column=1, padx=10, pady=5)

# Font color selection // Sélection de la couleur de la police
tk.Label(root, text="Name Color").grid(row=9, column=0, padx=10, pady=5)
name_color_var = tk.StringVar(value="darkblue")
name_color_button = tk.Button(root, text="Select Color", command=lambda: name_color_var.set(select_color()))
name_color_button.grid(row=9, column=1, padx=10, pady=5)

tk.Label(root, text="Title Color").grid(row=10, column=0, padx=10, pady=5)
title_color_var = tk.StringVar(value="darkred")
title_color_button = tk.Button(root, text="Select Color", command=lambda: title_color_var.set(select_color()))
title_color_button.grid(row=10, column=1, padx=10, pady=5)

tk.Label(root, text="Company Color").grid(row=11, column=0, padx=10, pady=5)
company_color_var = tk.StringVar(value="darkgreen")
company_color_button = tk.Button(root, text="Select Color", command=lambda: company_color_var.set(select_color()))
company_color_button.grid(row=11, column=1, padx=10, pady=5)

# Background color selection // Sélection de la couleur de fond
tk.Label(root, text="Background Color").grid(row=12, column=0, padx=10, pady=5)
bg_color_var = tk.StringVar(value="#ADD8E6")  # Default light blue // Bleu clair par défaut
bg_color_button = tk.Button(root, text="Select Color", command=lambda: bg_color_var.set(select_color()))
bg_color_button.grid(row=12, column=1, padx=10, pady=5)

# Background image selection // Sélection de l'image de fond
tk.Label(root, text="Background Image").grid(row=13, column=0, padx=10, pady=5)
bg_image_path_var = tk.StringVar()
bg_image_button = tk.Button(root, text="Select Image", command=lambda: bg_image_path_var.set(select_background_image()))
bg_image_button.grid(row=13, column=1, padx=10, pady=5)

# Preview and Save buttons // Boutons de prévisualisation et de sauvegarde
preview_button = tk.Button(root, text="Preview", command=preview_card)
preview_button.grid(row=14, column=0, padx=10, pady=10)

save_button = tk.Button(root, text="Save", command=save_card)
save_button.grid(row=14, column=1, padx=10, pady=10)

# Start the main loop // Démarre la boucle principale
root.mainloop()