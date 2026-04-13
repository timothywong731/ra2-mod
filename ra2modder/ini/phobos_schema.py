# Phobos extension tags for RA2/YR
# Source: Phobos documentation (https://phobos.readthedocs.io/)
#
# Phobos is a companion extension to Ares (NOT a replacement).
# Format: { "TagName": ("type", "default", "description", "applies_to") }

PHOBOS_TAGS: dict[str, tuple[str, str, str, str]] = {
    # -- Shield System --
    "Shield.Strength": ("int", "0", "Shield hit points", "TechnoType"),
    "Shield.Armor": ("ArmorType", "none", "Shield armor type", "TechnoType"),
    "Shield.InheritArmorFromTechno": ("bool", "no", "Shield uses techno's armor", "TechnoType"),
    "Shield.Powered": ("bool", "no", "Shield requires power", "TechnoType"),
    "Shield.Respawn": ("bool", "no", "Shield regenerates", "TechnoType"),
    "Shield.Respawn.Duration": ("int", "0", "Frames to fully regenerate", "TechnoType"),
    "Shield.Respawn.Amount": ("int", "0", "HP regenerated per tick", "TechnoType"),
    "Shield.Respawn.Rate": ("int", "0", "Frames between regen ticks", "TechnoType"),
    "Shield.SelfHealing": ("bool", "no", "Shield self-heals over time", "TechnoType"),
    "Shield.SelfHealing.Amount": ("int", "0", "HP healed per tick", "TechnoType"),
    "Shield.SelfHealing.Rate": ("int", "0", "Frames between heal ticks", "TechnoType"),
    "Shield.AbsorbOverDamage": ("bool", "no", "Shield absorbs all damage when broken", "TechnoType"),
    "Shield.BreakWeapon": ("WeaponType", "", "Weapon detonated when shield breaks", "TechnoType"),
    "Shield.IdleAnim": ("AnimType", "", "Animation while shield is active", "TechnoType"),
    "Shield.BreakAnim": ("AnimType", "", "Animation when shield breaks", "TechnoType"),
    "Shield.HitAnim": ("AnimType", "", "Animation when shield is hit", "TechnoType"),

    # -- DigitalDisplay --
    "DigitalDisplay.Enable": ("bool", "no", "Show digital HP/Shield display", "TechnoType"),
    "DigitalDisplay.Text.Color": ("color", "green", "Text color for display", "TechnoType"),
    "DigitalDisplay.Offset": ("point", "0,0", "Pixel offset for display", "TechnoType"),
    "DigitalDisplayType": ("string", "", "Custom display type definition", "TechnoType"),

    # -- AttachEffect --
    "AttachEffect.Duration": ("int", "0", "Duration of attached effect in frames", "WarheadType"),
    "AttachEffect.Animation": ("AnimType", "", "Animation while effect is active", "WarheadType"),
    "AttachEffect.SpeedMultiplier": ("float", "1.0", "Speed multiplier while affected", "WarheadType"),
    "AttachEffect.ArmorMultiplier": ("float", "1.0", "Armor multiplier while affected", "WarheadType"),
    "AttachEffect.FirepowerMultiplier": ("float", "1.0", "Firepower multiplier while affected", "WarheadType"),
    "AttachEffect.ROFMultiplier": ("float", "1.0", "Rate of Fire multiplier", "WarheadType"),
    "AttachEffect.Cloakable": ("bool", "", "Override cloakable status", "WarheadType"),

    # -- LaserTrail --
    "LaserTrail.Types": ("list", "", "Laser trail type indices", "ProjectileType"),

    # -- Interceptor --
    "Interceptor": ("bool", "no", "Whether this weapon intercepts projectiles", "TechnoType"),
    "Interceptor.GuardRange": ("int", "0", "Range to scan for projectiles", "TechnoType"),
    "Interceptor.MinimumGuardRange": ("int", "0", "Minimum range to intercept", "TechnoType"),
    "Interceptor.EliteGuardRange": ("int", "0", "Elite range to scan", "TechnoType"),

    # -- Trajectory --
    "Trajectory.Speed": ("float", "100.0", "Custom trajectory speed", "ProjectileType"),
    "Trajectory.Type": ("string", "", "Custom trajectory type (Straight, Bombard)", "ProjectileType"),
    "Trajectory.Bombard.Height": ("int", "0", "Bombard trajectory height", "ProjectileType"),

    # -- Strafing --
    "Strafing": ("bool", "no", "Aircraft strafing mode", "AircraftType"),
    "Strafing.Shots": ("int", "5", "Number of strafing shots per run", "AircraftType"),
    "Strafing.UseAmmo": ("bool", "no", "Strafing uses ammo count", "AircraftType"),

    # -- Auto Death --
    "AutoDeath.Behavior": ("string", "", "Auto-death behavior (kill, vanish, sell)", "TechnoType"),
    "AutoDeath.OnAmmoDepletion": ("bool", "no", "Die when ammo runs out", "TechnoType"),
    "AutoDeath.AfterDelay": ("int", "0", "Die after this many frames", "TechnoType"),
    "AutoDeath.TechnosDontExist": ("list", "", "Die if none of these types exist", "TechnoType"),
    "AutoDeath.TechnosExist": ("list", "", "Die if any of these types exist", "TechnoType"),

    # -- Convert --
    "Convert.Script": ("string", "", "TeamScript to apply after conversion", "TechnoType"),
}
