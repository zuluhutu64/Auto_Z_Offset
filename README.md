## What's Different THIS time AGAIN? <br>
Keeping up with the 'fork of a fork of a fork of a fork...'-spirit, I've forked this project to fix a bug I had related to probe positioning in klipper.
The original code didn't seem to work with my version of klipper (At least with my BL Touch). So I rewrote the probing section to use the onboard ProbeHelper class.

  ## New Requirements:
  1) Physical Z-Endstop mounted as a pin - it is our reference point and is always Z 0.0 for calculations.
  2) BLTouch as probe - the sensor to check the distance between endstop and bed to calc the offset
  3) Accurate X and Y probe offsets
  4) configured [save_z_home]
  5) updateded parameters in [auto_offset_x]

You have to update the parameters in printer.cfg. The probe points are now stored in probe_points

<pre><code>
[auto_offset_z]
speed: 50                       # X/Y travel speed between the two points
ignore_alignment: False         # Optional - this allows ignoring the presence of z-tilt or quad gantry leveling config section
offset_min: -1                  # Optional - by default -1 is used - used as failsave to raise an error if offset is lower than this value
offset_max: 1                   # Optional - by default 1 is used - used as failsave to raise an error if offset is higher than this value
endstop_min: 0                  # Optional - by default disabled (0) - used as failsave to raise an error if endstop is lower than this value
endstop_max: 0                  # Optional - by default disabled (0) - used as failsave to raise an error if endstop is higher than this value
offsetadjust: 0.045             # Manual offset correction option - start with zero and optimize during print with babysteps
                                #  1) If you need to lower the nozzle from -0.71 to -0.92 for example your value is -0.21.
                                #  2) If you need to move more away from bed add a positive value.
horizontal_move_z: 5            #for probe_points_helper, was z_hop parameter
probe_points: -8, 77            #for probe_points_helper, First line: Physical endstop nozzle over pin, 2nd: Center of bed for example
        150,150 
endstopswitch: 0.5             #was hardcoded, now as config parameter. Distance of switch trigger point
</code></pre>

## Hints for setting using this extra:

After doing a first calibration, test the offset with the classic paper test. Probably you have to adjust "offsetadjust" for the trigger distance of your z-endstop.

### ***v-------forked readme-------v***

## What's Different THIS time? <br>
Keeping up with the 'fork of a fork of a fork of a fork...'-spirit, I've forked this project to fix a bug I had related to probe positioning in klipper.
I actually made this fix a while ago before uploading it, so it's missing a bit of refactoring recently done by the previous "forker" ([disPaw](https://github.com/disPaw)).
I do notice that there was an attempt in the previous fork to fix the same error but it does not seem to work for me on my fresh klipper installation.<br>
Considering that the original author of 'Auto_Z_Offset' has archived the repo, I might try to keep this fork updated and refactor it a bit... If I'm able to get over the fact that it's written in python :)<br>

### ***v-------forked readme-------v***

## What's Different? <br>
This is a fork of [SkyShadex's Auto_Z_Offset](https://github.com/SkyShadex/Auto_Z_Offset) adaptation for the Ender 3 with BLTouch. . . which is a fork of [hawkeyexp's auto_offset_z](https://github.com/hawkeyexp/auto_offset_z) for CoreXY printers with BLTouch. . . which is probably forked from elsewhere, too. At any rate, I noticed the install.sh file might benefit from removal of Moonraker dummy services like [Protoloft's klipper_z_calibration](https://github.com/protoloft/klipper_z_calibration#moonraker-update-manager).

  ## New Requirements:
  1) Physical Z-Endstop mounted as a pin - it is our reference point and is always Z 0.0 for calculations.
  2) BLTouch as probe - the sensor to check the distance between endstop and bed to calc the offset
  3) Accurate X and Y probe offsets
  
  ## Notes:
   Your BLTouch and Nozzle should have litte to no offset in the Y position. We won't be able to move Y to find the Z-Endpin on a Bedslinger
    unless you mount the switch to the bed. But that requires cable management and addressing bed heat. Possible, Better, But not free!
   The bigger the offset, the bigger the pin has to be. Your Nozzle and BLTouch have to both be able to touch the pin off of the bed so
   
   ## Installation:
Login to your pi by ssh. Clone the repo to your homefolder with this command:

        
        cd /home/pi
        git clone https://github.com/SpookySnek/Auto_Z_Offset.git
        cd ~/Auto_Z_Offset
        ./install.sh
        

For further updates you can add it to moonraker's updated manager:

<pre><code>
[update_manager auto_offset_z]
type: git_repo
path: ~/Auto_Z_Offset
origin: https://github.com/SpookySnek/Auto_Z_Offset.git
install_script: install.sh
managed_services: klipper
</code></pre>

    

## Original:<br>
## This is a Klipper plugin for an auto calibration Z offset with a BLTouch (or possible inductive probe - check hints first!)

## Why:<br>

I was inspired to make this possible since i build my Voron V2.4 and wanted the ability to change my print surfaces without
recalibrate my z offset for every surface and possible temp cause i'm also printing more than abs and didn't want to switch
to a klicky probe for example :-) (yes - the way how the klicky probe handles the z offset is the same idea behind)

## Requirements:<br>

1) Physical Z-Endstop - it is our reference point and is always Z 0.0 for calculations.
2) BLTouch as probe - the sensor to check the distance between endstop and bed to calc the offset
3) QUAD_GANTRY_LEVEL or Z_TILT used (the plugin checks if qgl or z-tilt is applied to ensure gantry and bed are parallel for correct values)
4) Ensure you set you x and y offset correct cause the plugin usses this offsets to move the bltouch over the endstop pin!

## How it works:<br>

The bltouch will probe two points - top of endstop and surface of your bed to messure the distance. Now we have one problem:
the nozzle triggers the endstop the bltouch can only touch the top surface - to ensure a correct offset the plugin includes a move distance
of 0.5mm (spec value from omron switches used in voron builts) which is the way the microsowitch in the endstop needs to trigger BUT:
ususally a bit more than 0.5mm is needed to trigger correctly (~0.1x till ~0.2x in most cases depending on the used microswitch).
This last bit can be set manually during a print probe by adjusting with babysteps until offset is correct and adding this to the 
config section of the plugin.
<pre><code>

                                                    | |
                                      Nozzle        | |  BLTouch
                                      |_   _|        -
                                        \_/               

Bed                                      _ 
--------------------------------------- | | Endstop Pin
</code></pre>

## Configuration for klipper:

<pre><code>
[auto_offset_z]
center_xy_position:175,175      # Center of bed for example
endstop_xy_position:233.5,358   # Physical endstop nozzle over pin
speed: 100                      # X/Y travel speed between the two points
z_hop: 10                       # Lift nozzle to this value after probing and for move
z_hop_speed: 20                 # Hop speed of probe
ignore_alignment: False         # Optional - this allows ignoring the presence of z-tilt or quad gantry leveling config section
offset_min: -1                  # Optional - by default -1 is used - used as failsave to raise an error if offset is lower than this value
offset_max: 1                   # Optional - by default 1 is used - used as failsave to raise an error if offset is higher than this value
endstop_min: 0                  # Optional - by default disabled (0) - used as failsave to raise an error if endstop is lower than this value
endstop_max: 0                  # Optional - by default disabled (0) - used as failsave to raise an error if endstop is higher than this value
offsetadjust: 0.0               # Manual offset correction option - start with zero and optimize during print with babysteps
                                  1) If you need to lower the nozzle from -0.71 to -0.92 for example your value is -0.21.
                                  2) If you need to move more away from bed add a positive value.
</code></pre>

## Hints for use with an inductive probe:

in general an inductive probe should also work this way if it is able to detect the endstop pin but it is not tested and you have to
ensure the probe is really detecting the endstop pin and not the bed surface which is possible really close to the pin.

## Last words:

I'm not a software developer, only a guy which is playing arround to solve his problems or needs :-)
The code - i'm really sure - can be improved but it is running without problems for me now since some weeks.
If you wan't to give it a try have fun but note: if something is going wrong i'm not responsible for it!
