import socket
import struct

buffered_text = ""
fin_final = ""  # Acumula los terceros strings de cada paquete

class BoardItem:
    """Clase para representar un BoardItem de Intendix"""
    def __init__(self):
        self.enabled = False
        self.removable = False
        self.supports_double_security = False
        self.name = ""
        self.text = ""
        self.output_text = ""
        self.flash_image_filename = ""
        self.dark_image_filename = ""

def parse_dotnet_string(data, offset):
    """
    Lee un string del formato .NET Binary Serialization
    Formato: 0x06 [longitud] [bytes UTF-8]
    """
    if offset >= len(data):
        return None, offset
    
    if data[offset] == 0x06:
        offset += 1
        if offset >= len(data):
            return None, offset
        
        length = data[offset]
        offset += 1
        
        if offset + length > len(data):
            return None, offset
        
        string_bytes = data[offset:offset + length]
        offset += length
        
        try:
            return string_bytes.decode('utf-8'), offset
        except:
            return None, offset
    
    return None, offset

def deserialize_board_item(data):
    """
    Deserializa un BoardItem desde los bytes recibidos
    Extrae específicamente el tercer string válido (que es el carácter)
    """
    try:
        item = BoardItem()
        strings_found = []
        
        for i in range(len(data) - 50):
            if data[i] == 0x06:
                string_val, _ = parse_dotnet_string(data, i)
                if string_val is not None:
                    strings_found.append(string_val)
        
        if len(strings_found) >= 3:
            char = strings_found[2].strip()
            if char and (char.isalnum() or char in ['!', ' ', '.', ',', '?', ';']):
                item.output_text = char
                return item
        
        return None
        
    except Exception as e:
        print(f"   Error deserializando: {e}")
        return None

def listen_speller():
    global buffered_text, fin_final
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 1000))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print("Esperando datos del Speller Intendix...")
    print("Escribe algo en el Speller y termina con '!'")
    print("=" * 60)
    print()

    packet_count = 0

    while True:
        try:
            data, addr = sock.recvfrom(12264)
            packet_count += 1
            
            item = deserialize_board_item(data)
            
            if item and item.output_text:
                char = item.output_text.strip()
                
                if char:
                    print(f"Carácter recibido: '{char}'")
                    buffered_text += char
                    fin_final += char
                    
                    print(f"Buffer: {buffered_text}")
                    
                    if '!' in char:
                        buffered_text = buffered_text.replace('!', '')
                        fin_final = fin_final.replace('!', '')
                        print(f"\n¡Frase completa! -> {fin_final}")
                        print("=" * 60)
                        print()
                        buffered_text = ""
                        fin_final = ""
            else:
                print(f"⚠ Paquete #{packet_count}: No se pudo extraer texto")
                
                if packet_count <= 5:
                    print("Strings encontrados en el paquete:")
                    strings_found_debug = []
                    for i in range(len(data) - 50):
                        if data[i] == 0x06:
                            string_val, _ = parse_dotnet_string(data, i)
                            if string_val is not None:
                                strings_found_debug.append(string_val)
                                display = string_val if len(string_val) <= 30 else string_val[:30] + "..."
                                print(f"      [{len(strings_found_debug)}] '{display}'")
                    
                    # Concatenar el tercer string al fin_final si existe
                    if len(strings_found_debug) >= 3:
                        char3 = strings_found_debug[2].strip()
                        fin_final += char3
                        print(f"Tercer string acumulado (fin_final): '{fin_final}'")
                    print()
                
        except KeyboardInterrupt:
            print("\n\nCerrando...")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    listen_speller()
