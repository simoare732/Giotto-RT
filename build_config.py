import yaml
import datetime

def generate_header():
    # 1. Load the YAML file
    try:
        with open("config.yaml", "r") as yaml_file:
            config = yaml.safe_load(yaml_file)
    except FileNotFoundError:
        print("Error: The config.yaml file was not found.")
        return
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}")
        return

    # Safety checks
    if config is None:
        print("Error: The config.yaml file is empty.")
        return
    
    if not isinstance(config, dict):
        print("Error: The config.yaml file does not contain a valid dictionary structure.")
        return

    # 2. Create and write the C++ header file
    try:
        with open("mc/config.h", "w") as header_file:
            # Header with timestamp
            header_file.write("/*\n")
            header_file.write(f" * File automatically generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            header_file.write(" * WARNING: Do not modify this file manually.\n")
            header_file.write(" * Edit 'config.yaml' and regenerate using the Python script.\n")
            header_file.write(" */\n\n")
            
            # Include Guards to prevent multiple inclusions
            header_file.write("#ifndef CONFIG_H\n")
            header_file.write("#define CONFIG_H\n\n")

            # 3. Iterate over all sections of the YAML file
            for section, params in config.items():
                header_file.write(f"// --- {section.upper()} ---\n")
                
                if isinstance(params, dict):
                    for key, value in params.items():
                        # Convert key to UPPERCASE for C++ macros
                        macro_name = key.upper()
                        
                        # Strict type recognition
                        if isinstance(value, bool):
                            # Booleans in Python are subclasses of int, so they must be checked first
                            val_str = "true" if value else "false"
                        elif isinstance(value, float):
                            val_str = str(value)
                        elif isinstance(value, int):
                            # PyYAML automatically converts values like 0xFE to integers (254).
                            # Both are valid for the C++ compiler, but for readability we convert back to hex
                            # if we suspect it's a marker (based on the key name).
                            if "marker" in key.lower():
                                val_str = f"0x{value:02X}"
                            else:
                                val_str = str(value)
                        elif isinstance(value, str):
                            # If it's a string representing a hex (e.g., textual "0xFE")
                            if value.startswith("0x"):
                                val_str = value
                            else:
                                # Otherwise, wrap it in double quotes for C++
                                val_str = f'"{value}"'
                        else:
                            val_str = str(value)
                            
                        # Write the directive
                        header_file.write(f"#define {macro_name} {val_str}\n")
                header_file.write("\n")

            header_file.write("#endif // CONFIG_H\n")
            print("Success: 'config.h' generated successfully for all variables!")
            
    except Exception as e:
        print(f"Error while writing to config.h: {e}")

if __name__ == "__main__":
    generate_header()