# worker.py

import os
import re
import wmi
import string
import logging
import pythoncom
import subprocess
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal

class Worker(QThread):
    log_signal = pyqtSignal(str)
    data_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    load_finished_signal = pyqtSignal()
    multiple_data_partitions_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._setup_logger()

        self.is_running = True
        self.disk_count = 0
        self.progress_value = 0
        self.target_disk = None
        self.data_disk = None
        self.target_volume = None
        self.data_volume = None
        self.boot_volume = None
        self.nvmes = []
        self.ssds = []
        self.hdds = []
        self.path = 0
        self.save = True
        self.stage1 = None
        self.stage2 = None
        self.stage3 = None

    def _setup_logger(self):
        """로그 파일 설정을 초기화하는 함수"""
        log_file = 'log.txt'
        if os.path.exists(log_file):
            os.remove(log_file)
        
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _run_command(self, command, on_stdout=None):
        logging.debug(f"Executing command: {command}")
        try:
            process = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.current_process = process # --- [로직 추가] ---

            while self.is_running:
                output = process.stdout.readline()
                if output and on_stdout:
                    on_stdout(output)
                if output == '' and process.poll() is not None:
                    break
            
            rc = process.poll()
            if rc != 0 and self.is_running: # 중지 버튼으로 종료된 경우는 오류 로그를 남기지 않음
                error_output = process.stderr.read()
                self.log_signal.emit(f"오류 발생 (코드: {rc}): {command}\n{error_output}")
            return rc == 0
        finally:
            self.current_process = None # --- [로직 추가] ---

    def set_selected_data_volume(self, volume_number):
        """사용자가 선택한 데이터 볼륨을 설정하고 데이터 보존을 활성화합니다."""
        logging.debug(f"User selected data volume: {volume_number}")
        self.data_volume = volume_number
        if self.target_volume and self.data_volume:
            self.log_signal.emit("데이터 보존이 가능합니다.")
            self.data_signal.emit(True)

    def load(self):
        self.check_disk_count()
        self.find_volumes_and_folders()
        self.categorize_disks()
        self.load_finished_signal.emit()

    def run(self):
        self.log_signal.emit("작업이 시작되었습니다.")
        if self.path == 0:
            self.log_signal.emit("현재 시스템을 업무용으로 초기화합니다.")
        elif self.path == 1:
            self.log_signal.emit("현재 시스템을 인터넷용으로 초기화합니다.")
        elif self.path == 2:
            self.log_signal.emit("현재 시스템을 출장용으로 초기화합니다.")
        else :
            self.log_signal.emit("현재 시스템을 K자회사용으로 초기화합니다.")

        self.remove_drive_letter()
        self.run_format()
        if self.stage1:
            self.apply_wim()
        if self.stage2:
            self.set_kdic_folder()
            self.set_drivers()
            self.copy_drivers()
            self.set_boot()
        if self.stage3:
            self.set_unattend()

    def run_diskpart(self, commands):
        logging.debug(f"Executing diskpart script:\n--- SCRIPT ---\n{commands}\n--------------")
        try:
            process = subprocess.Popen(["diskpart"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.current_process = process # --- [로직 추가] ---
            stdout, stderr = process.communicate(input=commands)
            return stdout
        finally:
            self.current_process = None # --- [로직 추가] ---

    def run_format(self):
        script_file = 'diskpart_script.txt'
        script_lines = None

        if self.save and self.target_volume and self.data_volume:
            script_lines = [
                f"select volume {self.target_volume}", "format fs=ntfs label=OS quick", "assign letter=C",
                f"select volume {self.data_volume}", "assign letter=D",
                f"select volume {self.boot_volume}", "format fs=fat32 quick", "assign letter=Z"
            ]
        elif self.disk_count == 1 and self.target_disk:
            script_lines = [
                f"select disk {self.target_disk}", "clean", "convert gpt", "create partition EFI size=100",
                "format fs=fat32 quick", "assign letter=Z", "create partition primary size=153601",
                "format fs=ntfs label=OS quick", "assign letter=C", "create partition primary",
                "format fs=ntfs label=DATA quick", "assign letter=D", "exit"
            ]
        elif self.disk_count > 1 and self.target_disk and self.data_disk:
            script_lines = [
                f"select disk {self.target_disk}", "clean", "convert gpt", "create partition EFI size=100",
                "format fs=fat32 quick", "assign letter=Z", "create partition primary",
                "format fs=ntfs label=OS quick", "assign letter=C",
                f"select disk {self.data_disk}", "clean", "convert gpt", "create partition primary",
                "format fs=ntfs label=DATA quick", "assign letter=D", "exit"
            ]
        else:
            self.log_signal.emit("디스크 정보를 찾지 못 했습니다.")
            return

        try:
            with open(script_file, 'w') as file:
                file.write("\n".join(script_lines) + "\n")
            command = f'diskpart /s {script_file}'
            if self._run_command(command):
                self.stage1 = True
                self.progress_signal.emit(self.progress_value + 1)
            else:
                self.log_signal.emit("디스크 포맷에 실패했습니다.")
        except Exception as e:
            self.log_signal.emit(f'Diskpart Script 실행에 실패했습니다. Code : {e}')
        finally:
            if os.path.exists(script_file):
                os.remove(script_file)

    def apply_wim(self):
        wim_path = self.set_image_path()
        self.log_signal.emit(f'현재 시스템에 {os.path.basename(wim_path)} 이미지를 적용합니다.')
        info_file = r'..\wim\info.txt'
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                info_lines = f.readlines()
            info_dict = {line.split(":", 1)[0].strip().lower(): line.split(":", 1)[1].strip() for line in info_lines if ":" in line}
            key_mapping = {0: "업무용", 1: "인터넷용", 2: "출장용", 3:"K자회사"}
            description = info_dict.get(key_mapping.get(self.path, ""), "")
            if description:
                self.log_signal.emit(description)
        except Exception as e:
            self.log_signal.emit(f"이미지 설명을 읽어오는데 실패했습니다: {e}")
        dism_command = f'dism /Apply-Image /ImageFile:{wim_path} /Index:1 /ApplyDir:C:\\ /BootDir:Z:\\ /Unattend:..\\unattend\\unattend.xml'
        def progress_callback(output):
            if "[" in output and self.progress_value < 98:
                self.progress_value += 1
                self.progress_signal.emit(self.progress_value)
        self.stage2 = self._run_command(dism_command, progress_callback)

    def set_drivers(self):
        driver_path = self.get_driver_path()
        driver_command = rf'dism /add-driver /image:C:\ /driver:"..\drivers\{driver_path}" /Recurse'
        self._run_command(driver_command)

    def copy_drivers(self):
        driver_path = self.get_driver_path()
        source_path = rf'..\drivers\{driver_path}'
        destination_path = r'C:\SEPR\Drivers'
        copy_command = f'robocopy "{source_path}" "{destination_path}" /E /COPYALL /XJ'
        self._run_command(copy_command)

    def set_boot(self):
        bcd_command = r'bcdboot C:\Windows /s Z: /f UEFI'
        self.stage3 = self._run_command(bcd_command, lambda out: self.log_signal.emit(out.strip()))
        if self.stage3:
            self.progress_value = 99
            self.progress_signal.emit(self.progress_value)
    
    def set_kdic_folder(self):
        source_path = r'C:\Users\kdic'
        destination_path = r'D:\kdic'
        copy_command = f'robocopy "{source_path}" "{destination_path}" /E /COPYALL /XJ'
        self._run_command(copy_command)

    def set_unattend(self):
        if self.stage3:
            source_path = r'..\wim\unattend.xml'
            destination_path = r'C:\windows\system32\sysprep\unattend.xml'
            copy_command = f'copy "{source_path}" "{destination_path}"'
            def unattend_callback(output):
                if output:
                    self.log_signal.emit(output.strip())
            if self._run_command(copy_command, unattend_callback):
                self.progress_signal.emit(100)
                self.log_signal.emit("모든 과정이 완료 되었습니다.")
                self.log_signal.emit("3초후 재부팅을 진행합니다.")
                shutdown_command = 'shutdown /r /t 3'
                logging.debug(f"Executing command: {shutdown_command}")
                os.system(shutdown_command)

    def set_image_path(self):
        paths = [r'..\wim\work.wim', r'..\wim\internet.wim', r'..\wim\trip.wim', r'..\wim\krnc.wim']
        return paths[self.path]

    def get_driver_path(self):
        pythoncom.CoInitialize()
        c = wmi.WMI()
        path = ""
        for board in c.Win32_BaseBoard():
            path = board.Product
        pythoncom.CoUninitialize()
        path = re.sub(r'[\\/:*<>|]', '', path)
        return path

    def assign_drive_letter(self, volume_number, letter):
        command = f"select volume {volume_number}\nassign letter={letter}\n"
        self.run_diskpart(command)

    def remove_drive_letter(self):
        for letter in ["C", "D", "Z"]:
            command = f"select volume {letter}\nremove letter={letter}\n"
            self.run_diskpart(command)

    def check_folders(self, drive_letter):
        path_prefix = f"{drive_letter}:\\"
        sysprep_path = os.path.join(path_prefix, "Windows", "system32", "sysprep")
        system_ini_path = os.path.join(path_prefix, "Users", "kdic", "desktop", "desktop.ini")
        is_system_partition = os.path.isdir(sysprep_path) and os.path.isfile(system_ini_path)
        data_ini_path = os.path.join(path_prefix, "kdic", "desktop", "desktop.ini")
        is_data_partition = os.path.isfile(data_ini_path)
        return is_system_partition, is_data_partition

    def find_available_letter(self, used_letters):
        available = sorted(set(string.ascii_uppercase) - used_letters)
        return available[0] if available else None

    def find_volumes_and_folders(self):
        list_vol_output = self.run_diskpart('list vol')
        volumes = []
        used_letters = set()
        for line in list_vol_output.splitlines():
            if "볼륨" not in line or "###" in line:
                continue
            parts = line.split()
            volume_number = parts[1]
            letter = parts[2] if len(parts) > 2 and len(parts[2]) == 1 else None
            volumes.append({"number": volume_number, "letter": letter})
            if letter:
                used_letters.add(letter)
        for vol in volumes:
            if vol["letter"] is None:
                available_letter = self.find_available_letter(used_letters)
                if available_letter:
                    self.assign_drive_letter(vol["number"], available_letter)
                    vol["letter"] = available_letter
                    used_letters.add(available_letter)
        error_message = None
        found_data_partitions = []
        for vol in volumes:
            letter = vol["letter"]
            if not letter:
                continue
            is_system_partition, is_data_partition = self.check_folders(letter)
            if is_system_partition:
                if self.target_volume is not None:
                    error_message = f"오류: 시스템 파티션이 2개 이상 발견되었습니다. (기존: 볼륨 {self.target_volume}, 추가: 볼륨 {vol['number']})"
                    break
                self.target_volume = vol["number"]
                detail_lines = self.run_diskpart(f'select volume {self.target_volume}\ndetail disk').splitlines()
                for d_line in detail_lines:
                    if "볼륨" in d_line and "FAT" in d_line and "###" not in d_line:
                        self.boot_volume = d_line.split()[1]
                        break
            elif is_data_partition:
                ini_path = os.path.join(f"{letter}:\\", "kdic", "desktop", "desktop.ini")
                try:
                    mtime = os.path.getmtime(ini_path)
                    date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    found_data_partitions.append({
                        "number": vol["number"],
                        "letter": letter,
                        "date": date_str
                    })
                except OSError:
                    continue
        if error_message:
            self.log_signal.emit(error_message)
            self.log_signal.emit("데이터 보존이 불가능합니다. '데이터 삭제' 옵션을 선택하거나 디스크를 정리하십시오.")
            self.target_volume = None
            self.data_volume = None
        elif len(found_data_partitions) > 1:
            self.log_signal.emit(f"데이터 파티션이 {len(found_data_partitions)}개 발견되었습니다. 하나를 선택해주세요.")
            self.multiple_data_partitions_signal.emit(found_data_partitions)
        else:
            if len(found_data_partitions) == 1:
                self.data_volume = found_data_partitions[0]['number']
            if self.target_volume and self.data_volume:
                self.log_signal.emit("데이터 보존이 가능합니다.")
                self.data_signal.emit(True)
            else:
                self.log_signal.emit("데이터 보존이 불가능합니다.")
                self.data_signal.emit(False)
                self.save = False

    def check_disk_count(self):
        pythoncom.CoInitialize()
        c = wmi.WMI()
        disks = c.Win32_DiskDrive()
        self.disk_count = sum(1 for disk in disks if "Fixed" in disk.MediaType)
        pythoncom.CoUninitialize()

    def categorize_disks(self):
        list_disk_output = self.run_diskpart('list disk')
        disks = []
        for line in list_disk_output.splitlines():
            if "디스크" in line and "###" not in line:
                parts = line.split()
                if len(parts) > 3 and parts[3].isdigit():
                    size = int(parts[3])
                    unit = parts[4].upper() if len(parts) > 4 else "GB"
                    if unit == "TB":
                        size *= 1024
                    disks.append((parts[1], size))
        nvmes, ssds, hdds = [], [], []
        for index, size in disks:
            details = self.run_diskpart(f'sel disk {index}\ndetail disk')
            disk_type_line = ""
            for line in details.splitlines():
                if "유형" in line:
                    disk_type_line = line
                    break
            if "USB" in disk_type_line:
                continue
            elif "NVMe" in disk_type_line:
                nvmes.append((index, size))
            elif "RAID" in disk_type_line or "SATA" in disk_type_line:
                ssds.append((index, size))
            else:
                hdds.append((index, size))
        min_size_gb = 100
        valid_nvmes = [d for d in nvmes if d[1] >= min_size_gb]
        valid_ssds = [d for d in ssds if d[1] >= min_size_gb]
        valid_hdds = [d for d in hdds if d[1] >= min_size_gb]
        valid_nvmes.sort(key=lambda x: x[1])
        valid_ssds.sort(key=lambda x: x[1])
        valid_hdds.sort(key=lambda x: x[1])
        if valid_nvmes:
            self.target_disk = valid_nvmes[0][0]
        elif valid_ssds:
            self.target_disk = valid_ssds[0][0]
        elif valid_hdds:
            self.target_disk = valid_hdds[0][0]
        all_disk_lists = [nvmes, ssds, hdds]
        for disk_list in all_disk_lists:
            disk_list[:] = [d for d in disk_list if d[0] != self.target_disk]
        nvmes.sort(key=lambda x: x[1], reverse=True)
        ssds.sort(key=lambda x: x[1], reverse=True)
        hdds.sort(key=lambda x: x[1], reverse=True)
        if self.disk_count > 1:
            if nvmes:
                self.data_disk = nvmes[0][0]
            elif ssds:
                self.data_disk = ssds[0][0]
            elif hdds:
                self.data_disk = hdds[0][0]
        if not self.target_disk:
            self.log_signal.emit("설치 가능한 시스템 디스크(100GB 이상)가 없습니다.")

    def stop(self):
        """작업자 스레드를 중지하고 실행 중인 외부 프로세스를 강제 종료합니다."""
        if not self.is_running:
            return

        logging.debug("Stop requested by user.")
        self.is_running = False

        if self.current_process and self.current_process.poll() is None:
            logging.info(f"Attempting to terminate process with PID: {self.current_process.pid}")
            # 자식 프로세스까지 모두 강제 종료 (/T 옵션)
            kill_command = f"taskkill /F /PID {self.current_process.pid} /T"
            subprocess.run(kill_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.current_process = None