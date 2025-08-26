"""
Water Bodies Name Generator
Provides beautiful names from bodies of water around the world for git branch naming
"""
import random
from typing import List, Optional


# Comprehensive list of water bodies from around the world
WATER_BODIES = [
    # Oceans
    "pacific", "atlantic", "indian", "arctic", "southern",
    
    # Major Seas
    "mediterranean", "caribbean", "baltic", "coral", "aegean", "adriatic",
    "black", "caspian", "red", "north", "barents", "kara", "laptev",
    "east-siberian", "chukchi", "beaufort", "tasman", "weddell", "ross",
    "arabian", "andaman", "yellow", "east-china", "south-china", "java",
    "timor", "arafura", "banda", "celebes", "sulu", "philippine",
    
    # Great Lakes & Major Lakes
    "superior", "huron", "michigan", "erie", "ontario", "baikal",
    "tanganyika", "malawi", "victoria", "ladoga", "balkhash", "vostok",
    "titicaca", "nicaragua", "athabasca", "great-bear", "great-slave",
    "winnipeg", "crater", "tahoe", "geneva", "como", "garda",
    "constance", "neagh", "lomond", "ness", "windermere",
    
    # Major Rivers
    "amazon", "nile", "yangtze", "mississippi", "yenisei", "yellow",
    "ob", "parana", "congo", "amur", "lena", "mekong", "mackenzie",
    "niger", "murray", "tocantins", "volga", "indus", "brahmaputra",
    "ganges", "danube", "yukon", "rio-grande", "colorado", "columbia",
    "fraser", "st-lawrence", "rhine", "elbe", "oder", "vistula",
    "dnieper", "don", "kama", "pechora", "dvina", "thames", "severn",
    "shannon", "tagus", "ebro", "po", "arno", "tiber",
    
    # Bays & Gulfs
    "hudson", "bengal", "biscay", "fundy", "mexico", "alaska",
    "bothnia", "finland", "riga", "gdansk", "persian", "oman",
    "aden", "guinea", "carpentaria", "great-australian", "spencer",
    "st-vincent", "encounter", "jervis", "botany", "port-phillip",
    "bass", "cook", "hawke", "poverty", "hauraki",
    
    # Straits & Channels
    "gibraltar", "hormuz", "magellan", "bering", "torres", "malacca",
    "dover", "english", "irish", "st-george", "cook", "bass",
    "solomon", "makassar", "lombok", "sunda", "taiwan", "korea",
    "la-perouse", "tsugaru", "nemuro", "kunashir",
    
    # Famous Fjords
    "geiranger", "naeroy", "hardanger", "sogne", "lyse", "milford",
    "doubtful", "dusky", "kenai", "prince-william", "glacier",
    
    # Archipelagos & Island Seas
    "aegean", "ionian", "tyrrhenian", "ligurian", "alboran",
    "balearic", "sardinian", "sicilian", "cretan", "myrto",
    "icarian", "thracian", "marmara", "azov", "white",
    
    # Historical & Mythological Waters
    "styx", "lethe", "acheron", "cocytus", "phlegethon",
    "avalon", "camelot", "atlantis", "lemuria", "mu"
]


def get_random_water_name(exclude: Optional[List[str]] = None) -> str:
    """
    Get a random water body name for branch naming.
    
    Args:
        exclude: List of water names to exclude from selection
        
    Returns:
        A random water body name
    """
    available_names = WATER_BODIES.copy()
    
    if exclude:
        available_names = [name for name in available_names if name not in exclude]
    
    if not available_names:
        # Fallback to full list if all names are excluded
        available_names = WATER_BODIES
        
    return random.choice(available_names)


def get_water_names_by_type(water_type: str) -> List[str]:
    """
    Get water names filtered by type (for future categorization).
    
    Args:
        water_type: Type of water body ('ocean', 'sea', 'lake', 'river', etc.)
        
    Returns:
        List of water names matching the type
    """
    # For now, return all names. In future, could categorize by type
    return WATER_BODIES


def generate_branch_name(session_id: str, exclude_names: Optional[List[str]] = None) -> str:
    """
    Generate a git branch name using water body + session ID.
    
    Args:
        session_id: The session identifier
        exclude_names: Water names to exclude (already in use)
        
    Returns:
        Branch name in format: ai/{water-name}-{short-session-id}
        Example: ai/mediterranean-a7f2k9
    """
    water_name = get_random_water_name(exclude_names)
    short_session = session_id[:8] if len(session_id) > 8 else session_id
    
    return f"ai/{water_name}-{short_session}"


def extract_water_name_from_branch(branch_name: str) -> Optional[str]:
    """
    Extract the water name from a branch name.
    
    Args:
        branch_name: Branch name like 'ai/pacific-a7f2k9'
        
    Returns:
        Water name like 'pacific', or None if not a water-named branch
    """
    if not branch_name.startswith("ai/"):
        return None
        
    # Remove 'ai/' prefix
    name_part = branch_name[3:]
    
    # Find the last hyphen to separate water name from session ID
    last_hyphen = name_part.rfind('-')
    if last_hyphen == -1:
        return name_part
        
    water_name = name_part[:last_hyphen]
    
    # Verify it's a known water name
    if water_name in WATER_BODIES:
        return water_name
        
    return None


def get_water_info(water_name: str) -> dict:
    """
    Get additional information about a water body (future feature).
    
    Args:
        water_name: Name of the water body
        
    Returns:
        Dictionary with water body information
    """
    # Future: Could include location, type, fun facts, etc.
    return {
        "name": water_name,
        "display_name": water_name.replace("-", " ").title(),
        "emoji": "🌊",  # Default emoji, could be customized per type
        "type": "unknown"  # Future: categorize by ocean/sea/lake/river
    }


if __name__ == "__main__":
    # Test the naming system
    print("Sample water body names:")
    for _ in range(10):
        sample_session = f"session-{random.randint(1000, 9999)}"
        branch_name = generate_branch_name(sample_session)
        water_name = extract_water_name_from_branch(branch_name)
        info = get_water_info(water_name)
        
        print(f"  {branch_name} -> {info['display_name']} {info['emoji']}")