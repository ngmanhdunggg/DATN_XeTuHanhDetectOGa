import numpy as np
import time
from config import (
    KP, KD, MAX_STEER, MIN_SPEED, MAX_SPEED, STEER_SLOW_THRESHOLD,
    BOOST_FORWARD_DURATION, BOOST_BACKWARD_DURATION, BOOST_FORWARD_SPEED,
    BOOST_BACKWARD_SPEED, SPEED_THRESHOLD_MOVING, STALL_DELAY, MAX_STEER_FOR_BOOST
)

class MotionController:
    def __init__(self):
        self.last_error = 0.0
        self.boost_state = 0          # 0: normal, 1: boost forward, 2: boost backward, 3: ramp down
        self.boost_start_time = 0.0
        self.stall_start_time = None
        self.ramp_start_speed = 0.0
        self.ramp_target_speed = 0.0

    def compute_pid(self, current_error):
        """Tính góc lái từ sai số (PD)"""
        cmd_steer = KP * current_error + KD * (current_error - self.last_error)
        cmd_steer = np.clip(cmd_steer, -MAX_STEER, MAX_STEER)
        self.last_error = current_error
        return cmd_steer

    def compute_speed_from_steer(self, cmd_steer):
        """Tính tốc độ mong muốn dựa trên góc lái (càng cua chậm càng chậm)"""
        if abs(cmd_steer) > STEER_SLOW_THRESHOLD:
            speed_factor = 1 - ((abs(cmd_steer) - STEER_SLOW_THRESHOLD) / (MAX_STEER - STEER_SLOW_THRESHOLD))
            cmd_speed = MIN_SPEED + (MAX_SPEED - MIN_SPEED) * (speed_factor ** 2)
        else:
            cmd_speed = MAX_SPEED
        return cmd_speed

    def update_boost(self, actual_speed, cmd_speed, cmd_steer, current_time):
        """
        Cập nhật trạng thái boost dựa trên vận tốc thực và lệnh mong muốn.
        Trả về: final_speed (float)
        """
        need_move = (abs(actual_speed) < SPEED_THRESHOLD_MOVING and
                     cmd_speed > 0.1 and
                     abs(cmd_steer) <= MAX_STEER_FOR_BOOST)

        # Nếu đang boost nhưng góc lái quá lớn -> thoát boost
        if self.boost_state != 0 and abs(cmd_steer) > MAX_STEER_FOR_BOOST:
            self.boost_state = 0
            self.stall_start_time = None

        if need_move:
            if self.stall_start_time is None:
                self.stall_start_time = current_time
            elif (current_time - self.stall_start_time) >= STALL_DELAY:
                if self.boost_state == 0:
                    self.boost_state = 1
                    self.boost_start_time = current_time
                    print("[BOOST] Start boost forward")
        else:
            self.stall_start_time = None
            if self.boost_state != 0 and self.boost_state != 3:
                if self.boost_state == 1:
                    self.boost_state = 3
                    self.ramp_start_speed = BOOST_FORWARD_SPEED
                    self.ramp_target_speed = cmd_speed
                    self.boost_start_time = current_time
                elif self.boost_state == 2:
                    self.boost_state = 3
                    self.ramp_start_speed = abs(BOOST_BACKWARD_SPEED)
                    self.ramp_target_speed = cmd_speed
                    self.boost_start_time = current_time
                else:
                    self.boost_state = 0

        # Tính final_speed dựa trên trạng thái boost
        if self.boost_state == 0:
            final_speed = cmd_speed
        elif self.boost_state == 1:
            elapsed = current_time - self.boost_start_time
            if elapsed >= BOOST_FORWARD_DURATION:
                self.boost_state = 2
                self.boost_start_time = current_time
                final_speed = BOOST_BACKWARD_SPEED
            else:
                final_speed = BOOST_FORWARD_SPEED
        elif self.boost_state == 2:
            elapsed = current_time - self.boost_start_time
            if elapsed >= BOOST_BACKWARD_DURATION:
                self.boost_state = 1
                self.boost_start_time = current_time
                final_speed = BOOST_FORWARD_SPEED
            else:
                final_speed = BOOST_BACKWARD_SPEED
        elif self.boost_state == 3:
            elapsed = current_time - self.boost_start_time
            speed_decrement = (elapsed / 0.05) * 0.01   # ramp down logic giữ nguyên
            new_speed = self.ramp_start_speed - speed_decrement
            if new_speed <= self.ramp_target_speed:
                self.boost_state = 0
                final_speed = self.ramp_target_speed
            else:
                final_speed = new_speed
        else:
            final_speed = cmd_speed
        return final_speed

    def get_boost_state(self):
        return self.boost_state