# Perform an easy auto offset calibration with BLTouch or Probe and a physical Z endstop (CNC-style)
#
# Initially developed for use with BLTouch
#
# Copyright (C) 2022 Marc Hillesheim <marc.hillesheim@outlook.de>
#
# Forked by SpookySnek 12 August 2025
# Forked by Zuluhutu 13 September 2025
# Version 1.0.3-forked (Rewrote for using ProbeHelper)
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import math
from . import probe
 
class AutoOffsetZCalibration:
    def __init__(self, config):
        self.printer = config.get_printer()

        zconfig = config.getsection('stepper_z')
        self.max_z = zconfig.getfloat('position_max', note_valid=False)
        self.ignore_alignment = config.getboolean('ignore_alignment', False)
        self.endstop_pin = zconfig.get('endstop_pin')
        self.speed = config.getfloat('speed', 50.0, above=0.)
        self.offsetadjust = config.getfloat('offsetadjust', 0.0)
        self.offset_min = config.getfloat('offset_min', -1)
        self.offset_max = config.getfloat('offset_max', 1)
        self.endstop_min = config.getfloat('endstop_min', 0)
        self.endstop_max = config.getfloat('endstop_max', 0)
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_move = self.printer.lookup_object('gcode_move')
        #added
        self.endstopswitch = config.getfloat('endstopswitch', 0.5)
       
       # TODO: verify that z_hop section
        if config.has_section("safe_z_home"):
            safeZHome = config.getsection('safe_z_home')
            self.zHop = safeZHome.getfloat('z_hop', note_valid=False)
            # TODO: check if a possible valid offset is set 
            if (self.zHop == 0) or (self.zHop is None):
                raise config.error("AutoOffsetZ: z_hop has to be set in safe_z_home to avoid crashing the probe.")
        else:
            raise config.error("AutoOffsetZ: X safe_z_home has to be definied for save probing.")
            
        # check if a BLTouch is installed
        if config.has_section("bltouch"):
            bltouch = config.getsection('bltouch')
            self.x_offset = bltouch.getfloat('x_offset', note_valid=False)
            self.y_offset = bltouch.getfloat('y_offset', note_valid=False)
            # check if a possible valid offset is set for bltouch
            if ((self.x_offset == 0) and (self.y_offset == 0)):
                raise config.error("AutoOffsetZ: Check the x and y offset [bltouch] - they both appear to be zero.")
            # check if bltouch is set as endstop
            if ('virtual_endstop' in self.endstop_pin):
                raise config.error("AutoOffsetZ: BLTouch can't be used as a Z endstop with this command. Use a physical endstop instead.")

        # check if a probe is installed
        elif config.has_section("probe"):
            probeCfg = config.getsection('probe')
            self.x_offset = probeCfg.getfloat('x_offset', note_valid=False)
            self.y_offset = probeCfg.getfloat('y_offset', note_valid=False)
            # check if a possible valid offset is set for probe
            if ((self.x_offset == 0) and (self.y_offset == 0)):
                raise config.error("AutoOffsetZ: Check the x and y offset [probe] - they both appear to be zero.")
            # check if probe is set as endstop
            if ('virtual_endstop' in self.endstop_pin):
                raise config.error("AutoOffsetZ: Probe can't be used as z endstop. Use a physical endstop instead.")
        else:
            raise config.error("AutoOffsetZ: No BLTouch or probe configured in your system - check your setup.")

        # check if qgl or ztilt is available
        if config.has_section("quad_gantry_level"):
            self.adjusttype = "qgl"
        elif config.has_section("z_tilt"):
            self.adjusttype = "ztilt"
        elif self.ignore_alignment == 1:
            self.adjusttype = "ignore"
        else:
            raise config.error("AutoOffsetZ: Your config must include [quad_gantry_level] or [z_tilt].")

        #setting up probeHelper. Doing this after the other checks as the offsets are already loaded
        
        self.probePoints = config.getlists('probe_points', seps=(',', '\n'),
                                                parser=float, count=2)
        
        #somehow probeHelper doesn't respect the settings of the offsets. doing it manually.
        self.pointsEndstop = list(self.probePoints[0])
        self.pointsBed = list(self.probePoints[1])
        self.pointsEndstop[0] -= self.x_offset
        self.pointsEndstop[1] -= self.y_offset
        self.pointsBed[0] -= self.x_offset
        self.pointsBed[1] -= self.y_offset
        self.probePoints = (self.pointsEndstop,self.pointsBed)
        
        self.probe_helper = probe.ProbePointsHelper(config,self.probe_finalize, default_points=self.probePoints)
        self.probe_helper.minimum_points(2)
        #self.probe_helper.use_xy_offsets = True    #does this do anything at all??
        self.gcode.register_command("AUTO_OFFSET_Z", self.cmd_AUTO_OFFSET_Z, desc=self.cmd_AUTO_OFFSET_Z_help)

        logging.info("AutoOffsetZ: init done")




    # custom round operation based mathematically instead of python default cutting off
    def rounding(self,n, decimals=0):
        expoN = n * 10 ** decimals
        if abs(expoN) - abs(math.floor(expoN)) < 0.5:
            return math.floor(expoN) / 10 ** decimals
        return math.ceil(expoN) / 10 ** decimals

    def cmd_AUTO_OFFSET_Z(self, gcmd):
        # check if all axes are homed
        toolhead = self.printer.lookup_object('toolhead')
        curtime = self.printer.get_reactor().monotonic()
        kin_status = toolhead.get_kinematics().get_status(curtime)
        probe_obj = self.printer.lookup_object('probe', None)
        skip = 0

        # debug output start #
        # gcmd.respond_raw("AutoOffsetZ (Homeing Result): %s" % (kin_status))
        # debug output end #

        if ('x' not in kin_status['homed_axes'] or
            'y' not in kin_status['homed_axes'] or
            'z' not in kin_status['homed_axes']):
            raise gcmd.error("You must home X, Y and Z axes first")

        if self.adjusttype == "qgl":
            # debug output start #
            #gcmd.respond_raw("AutoOffsetZ (Alignment Type): %s" % (self.adjusttype))
            # debug output end #

            # check if qgl has applied
            alignment_status = self.printer.lookup_object('quad_gantry_level').get_status(gcmd)
            if alignment_status['applied'] != 1:
                raise gcmd.error("AutoOffsetZ: Perform quad gantry leveling first.")

        elif self.adjusttype == "ztilt":
            # debug output start #
            #gcmd.respond_raw("AutoOffsetZ (Alignment Type): %s" % (self.adjusttype))
            # debug output end #

            # check if ztilt has applied
            alignment_status = self.printer.lookup_object('z_tilt').get_status(gcmd)
            if alignment_status['applied'] != 1:
                raise gcmd.error("AutoOffsetZ: Perform Z tilt first.")

        elif self.adjusttype == "ignore":
            gcmd.respond_info("AutoOffsetZ: Ignoring alignment as requested in the config...")
        else:
            raise config.error("AutoOffsetZ: Your printer has no config for [quad_gantry_level] or [z_tilt] which is needed to work correctly.")

        # debug output start #
        # gcmd.respond_raw("AutoOffsetZ (Alignment Result): %s" % (alignment_status))
        # debug output end #

        gcmd_offset = self.gcode.create_gcode_command("SET_GCODE_OFFSET",
                                                      "SET_GCODE_OFFSET",
                                                      {'Z': 0})
        self.gcode_move.cmd_SET_GCODE_OFFSET(gcmd_offset)

        #start probing using the probe_helper class
        self.probe_helper.start_probe(gcmd)

    def probe_finalize(self, offsets, positions):
        # calcualtion offset
        
        logging.info("Calculating AutoOffsetZ  with (positions): %s", positions)
        logging.info("Calculating AutoOffsetZ  with (offsets): %s", offsets) 
     
        gcode = self.printer.lookup_object('gcode')
        
        zendstop = positions[0][2]
        zbed = positions[1][2]
        diffbedendstop = zendstop - zbed
        
        logging.info("Calculating AutoOffsetZ  with zbed: %s", zbed) 
        logging.info("Calculating AutoOffsetZ  with zendstop: %s", zendstop)
        logging.info("Calculating AutoOffsetZ  with diffbedendstop: %s", diffbedendstop) 
        
        offset = self.rounding((0 - diffbedendstop  + self.endstopswitch) + self.offsetadjust,3)
        logging.info("Calculating AutoOffsetZ  with (offset): %s", offset) 
        
        gcode.respond_info("AutoOffsetZ:\nBed: %.3f\nEndstop: %.3f\nDiff: %.3f\nManual Adjust: %.3f\nTotal Calculated Offset: %.3f" % (zbed,zendstop,diffbedendstop,self.offsetadjust,offset,))
               

        # failsave
        if offset < self.offset_min or offset > self.offset_max:
            raise gcode.error("AutoOffsetZ: Your calculated offset is out of config limits! (Min: %.3f mm | Max: %.3f mm) - abort..." % (self.offset_min,self.offset_max))

        if self.endstop_min != 0 and zendstop[2] < self.endstop_min:
            raise gcode.error("AutoOffsetZ: Your endstop value is out of config limits! (Min: %.3f mm | Meassured: %.3f mm) - abort..." % (self.endstop_min,zendstop[2]))

        if self.endstop_max != 0 and zendstop[2] > self.endstop_max:
            raise gcode.error("AutoOffsetZ: Your endstop value is out of config limits! (Max: %.3f mm | Meassured: %.3f mm) - abort..." % (self.endstop_max,zendstop[2]))

        self.set_offset(offset)


    cmd_AUTO_OFFSET_Z_help = "Test endstop and bed surface to calcualte g-code offset for Z"

    def set_offset(self, offset):
        # reset pssible existing offset to zero
        gcmd_offset = self.gcode.create_gcode_command("SET_GCODE_OFFSET",
                                                      "SET_GCODE_OFFSET",
                                                      {'Z': 0})
        self.gcode_move.cmd_SET_GCODE_OFFSET(gcmd_offset)
        # set new offset
        gcmd_offset = self.gcode.create_gcode_command("SET_GCODE_OFFSET",
                                                      "SET_GCODE_OFFSET",
                                                      {'Z': offset})
        self.gcode_move.cmd_SET_GCODE_OFFSET(gcmd_offset)


def load_config(config):
    return AutoOffsetZCalibration(config)
