# Ares 3.0 extension tags for RA2/YR
# Source: Ares documentation (https://ares-developers.github.io/Ares-docs/)
#
# Format: { "TagName": ("type", "default", "description", "applies_to") }
# applies_to: comma-separated list of section types
# (TechnoType, BuildingType, InfantryType, VehicleType, AircraftType,
#  WeaponType, WarheadType, ProjectileType, SuperWeaponType, General)

ARES_TAGS: dict[str, tuple[str, str, str, str]] = {
    # -- Armor / Verses --
    "Armor.DefaultForceShield": ("ArmorType", "special_1", "Default ForceShield armor type", "General"),
    "Versus.unknown.ForceFire": ("bool", "yes", "Whether ForceFire allows targeting this armor", "WarheadType"),
    "Versus.unknown.Retaliate": ("bool", "yes", "Whether AI retaliates against this armor", "WarheadType"),
    "Versus.unknown.PassiveAcquire": ("bool", "yes", "Whether AI auto-acquires this armor", "WarheadType"),

    # -- KillDriver --
    "KillDriver": ("bool", "no", "Whether this warhead ejects the driver", "WarheadType"),
    "KillDriver.KillBelowPercent": ("float", "1.0", "Only eject if target HP below percent", "WarheadType"),
    "CanDrive": ("bool", "no", "Whether this infantry can drive vehicles", "InfantryType"),
    "CanBeDriven": ("bool", "yes", "Whether this vehicle can be driven", "VehicleType"),

    # -- Hijacker enhancements --
    "Hijacker.Allowed": ("bool", "yes", "Whether this unit can be hijacked", "TechnoType"),
    "Hijacker.ChangeOwner": ("bool", "yes", "Whether hijacking changes owner", "InfantryType"),
    "Hijacker.CountInfantry": ("bool", "yes", "Whether hijacking counts for kill tracking", "InfantryType"),

    # -- Gunner / IFV --
    "Gunner": ("bool", "no", "Whether this is a Gunner-type IFV", "VehicleType"),
    "WeaponCount": ("int", "1", "Number of weapons in IFV weapon stages", "VehicleType"),

    # -- Type Conversion --
    "Convert.From": ("TechnoType", "", "Source type for conversion", "TechnoType"),
    "Convert.To": ("TechnoType", "", "Target type for conversion", "TechnoType"),

    # -- Custom Missiles --
    "MissileSpawn": ("bool", "no", "Treat as custom missile spawner", "TechnoType"),
    "MissileSpawnType": ("TechnoType", "", "Type to spawn as missile", "TechnoType"),

    # -- Prism Forwarding --
    "PrismForwarding": ("bool/values", "no", "Enable prism forwarding chain", "BuildingType"),
    "PrismForwarding.MaxFeeds": ("int", "-1", "Maximum buildings that can forward to this", "BuildingType"),
    "PrismForwarding.MaxChainLength": ("int", "-1", "Maximum chain length", "BuildingType"),
    "PrismForwarding.MaxNetworkSize": ("int", "-1", "Maximum total buildings in network", "BuildingType"),
    "PrismForwarding.SupportModifier": ("float", "1.0", "Damage modifier per support tower", "BuildingType"),

    # -- Spawner enhancements --
    "Spawner.ExtraLimitRange": ("int", "0", "Extra range limit for spawned units", "TechnoType"),
    "Spawns.Delay": ("int", "0", "Delay between spawning units", "TechnoType"),

    # -- Secret Lab --
    "SecretLab.PossibleBoons": ("list", "", "Comma-separated list of possible secret lab rewards", "BuildingType"),
    "SecretLab.GenerateOnCapture": ("bool", "no", "Whether to re-generate boon when captured", "BuildingType"),

    # -- Tunnel --
    "IsTunnelEntrance": ("bool", "no", "Whether this building is a tunnel entrance", "BuildingType"),
    "Tunnel.MaxPassengers": ("int", "0", "Max passengers in tunnel network", "BuildingType"),

    # -- Operator --
    "Operator": ("bool", "no", "Whether this unit requires an operator", "TechnoType"),
    "Operator.Type": ("InfantryType", "", "Required operator type", "TechnoType"),

    # -- Bounty --
    "Bounty": ("bool", "no", "Whether killing this gives bounty", "TechnoType"),
    "Bounty.Value": ("int", "0", "Credits to award", "TechnoType"),
    "Bounty.Display": ("bool", "yes", "Whether to show bounty text", "TechnoType"),

    # -- Death weapon --
    "DeathWeapon": ("WeaponType", "", "Weapon fired on death", "TechnoType"),
    "DeathWeapon.Damage": ("int", "0", "Override damage for death weapon", "TechnoType"),

    # -- Factory Plant --
    "FactoryPlant.AffectedTypes": ("list", "", "Types affected by factory plant discount", "BuildingType"),

    # -- MIX loading / includes --
    "IncludeFile": ("string", "", "Extra INI file to include (Ares-specific)", "General"),

    # -- Cameo --
    "CameoPCX": ("string", "", "PCX file to use as cameo icon", "TechnoType"),
    "AltCameoPCX": ("string", "", "PCX file for alternate cameo", "TechnoType"),
}
