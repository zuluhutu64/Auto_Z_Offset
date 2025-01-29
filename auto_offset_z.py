# Perform an easy auto offset calibration with BLTouch or Probe and a physical Z endstop (CNC-style)
#
# Initially developed for use with BLTouch
#
# Copyright (C) 2022 Marc Hillesheim <marc.hillesheim@outlook.de>
#
# Version 0.0.4 / 12.03.2022
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from . import probe
import math

class AutoOffsetZCalibration:
    def __init__(self, config):
        self.printer = config.get_printer()
        x_pos_center, y_pos_center = config.getfloatlist("center_xy_position", count=2)
        x_pos_endstop, y_pos_endstop = config.getfloatlist("endstop_xy_position", count=2)
        self.center_x_pos, self.center_y_pos = x_pos_center, y_pos_center
        self.endstop_x_pos, self.endstop_y_pos = x_pos_endstop, y_pos_endstop
        self.z_hop = config.getfloat("z_hop", default=10.0)
        self.z_hop_speed = config.getfloat('z_hop_speed', 15., above=0.)
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
        self.gcode.register_command("AUTO_OFFSET_Z", self.cmd_AUTO_OFFSET_Z, desc=self.cmd_AUTO_OFFSET_Z_help)

        # check if a BLTouch is installed
        if config.has_section("bltouch"):
            bltouch = config.getsection('bltouch')
            self.x_offset = bltouch.getfloat('x_offset', note_valid=False)
            self.y_offset = bltouch.getfloat('y_offset', note_valid=False)
            if (self.x_offset == 0 and self.y_offset == 0):
                raise config.error("AutoOffsetZ: Check the x and y offset [bltouch] - they both appear to be zero.")
            if 'virtual_endstop' in self.endstop_pin:
                raise config.error("AutoOffsetZ: BLTouch can't be used as a Z endstop with this command. Use a physical endstop instead.")

        # check if a probe is installed
        elif config.has_section("probe"):
            probe = config.getsection('probe')
            self.x_offset = probe.getfloat('x_offset', note_valid=False)
            self.y_offset = probe.getfloat('y_offset', note_valid=False)
            if (self.x_offset == 0 and self.y_offset == 0):
                raise config.error("AutoOffsetZ: Check the x and y offset [probe] - they both appear to be zero.")
            if 'virtual_endstop' in self.endstop_pin:
                raise config.error("AutoOffsetZ: Probe can't be used as a Z endstop. Use a physical endstop instead.")
        else:
            raise config.error("AutoOffsetZ: No BLTouch or probe configured in your system.")

        if config.has_section("quad_gantry_level"):
            self.adjusttype = "qgl"
        elif config.has_section("z_tilt"):
            self.adjusttype = "ztilt"
        elif self.ignore_alignment:
            self.adjusttype = "ignore"
        else:
            raise config.error("AutoOffsetZ: Your config must include [quad_gantry_level] or [z_tilt].")

    def rounding(self, n, decimals=0):
        expoN = n * 10 ** decimals
        if abs(expoN) - abs(math.floor(expoN)) < 0.5:
            return math.floor(expoN) / 10 ** decimals
        return math.ceil(expoN) / 10 ** decimals

    def cmd_AUTO_OFFSET_Z(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')
        curtime = self.printer.get_reactor().monotonic()
        kin_status = toolhead.get_kinematics().get_status(curtime)

        if 'x' not in kin_status['homed_axes'] or 'y' not in kin_status['homed_axes'] or 'z' not in kin_status['homed_axes']:
            raise gcmd.error("You must home X, Y, and Z axes first.")

        if self.adjusttype == "qgl":
            alignment_status = self.printer.lookup_object('quad_gantry_level').get_status(gcmd)
            if alignment_status['applied'] != 1:
                raise gcmd.error("AutoOffsetZ: Perform quad gantry leveling first.")

        elif self.adjusttype == "ztilt":
            alignment_status = self.printer.lookup_object('z_tilt').get_status(gcmd)
            if alignment_status['applied'] != 1:
                raise gcmd.error("AutoOffsetZ: Perform Z tilt first.")

        elif self.adjusttype == "ignore":
            gcmd.respond_info("AutoOffsetZ: Ignoring alignment as per configuration.")

        self.gcode_move.cmd_SET_GCODE_OFFSET(self.gcode.create_gcode_command("SET_GCODE_OFFSET", "SET_GCODE_OFFSET", {'Z': 0}))

        gcmd.respond_info("AutoOffsetZ: Probing endstop...")
        toolhead.manual_move([self.endstop_x_pos - self.x_offset, self.endstop_y_pos - self.y_offset], self.speed)
        zendstop = self.printer.lookup_object('toolhead').probe_position()  # Updated to align with the latest probe method
        if self.z_hop:
            toolhead.manual_move([None, None, self.z_hop], self.z_hop_speed)

        gcmd.respond_info("AutoOffsetZ: Probing bed...")
        toolhead.manual_move([self.center_x_pos - self.x_offset, self.center_y_pos - self.y_offset], self.speed)
        zbed = self.printer.lookup_object('toolhead').probe_position()  # Updated to align with the latest probe method
        if self.z_hop:
            toolhead.manual_move([None, None, self.z_hop], self.z_hop_speed)

        endstopswitch = 0.5
        diffbedendstop = zendstop[2] - zbed[2]
        offset = self.rounding((0 - diffbedendstop + endstopswitch) + self.offsetadjust, 3)

        gcmd.respond_info(f"AutoOffsetZ:\nBed: {zbed[2]:.3f}\nEndstop: {zendstop[2]:.3f}\nDiff: {diffbedendstop:.3f}\nManual Adjust: {self.offsetadjust:.3f}\nTotal Calculated Offset: {offset:.3f}")

        if offset < self.offset_min or offset > self.offset_max:
            raise gcmd.error(f"AutoOffsetZ: Calculated offset is out of limits (Min: {self.offset_min:.3f} mm | Max: {self.offset_max:.3f} mm). Aborting...")

        if self.endstop_min != 0 and zendstop[2] < self.endstop_min:
            raise gcmd.error(f"AutoOffsetZ: Endstop value is below limit (Min: {self.endstop_min:.3f} mm | Measured: {zendstop[2]:.3f} mm). Aborting...")

        if self.endstop_max != 0 and zendstop[2] > self.endstop_max:
            raise gcmd.error(f"AutoOffsetZ: Endstop value is above limit (Max: {self.endstop_max:.3f} mm | Measured: {zendstop[2]:.3f} mm). Aborting...")

        self.set_offset(offset)

    cmd_AUTO_OFFSET_Z_help = "Test endstop and bed surface to calculate G-code offset for Z."

    def set_offset(self, offset):
        self.gcode_move.cmd_SET_GCODE_OFFSET(self.gcode.create_gcode_command("SET_GCODE_OFFSET", "SET_GCODE_OFFSET", {'Z': 0}))
        self.gcode_move.cmd_SET_GCODE_OFFSET(self.gcode.create_gcode_command("SET_GCODE_OFFSET", "SET_GCODE_OFFSET", {'Z': offset}))

def load_config(config):
    return AutoOffsetZCalibration(config)
