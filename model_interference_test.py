
import os
import signal
import time
import subprocess
import datetime
import time
import logging
import system_tracker as sys_track
import numpy as np
import copy

googlenet_cmd = ['python', 'image_classifier.py', '--model', 'googlenet', '--use_cuda', 'True']
mobilenetv2_cmd = ['python', 'image_classifier.py', '--model', 'mobilenet', '--use_cuda', 'True']
vgg19_cmd = ['python', 'image_classifier.py', '--model', 'vgg19', '--use_cuda', 'True']
pos_cmd = ['python', 'languages.py', '--model', 'lstm', '--dataset', 'ud-eng', '--task', 'pos', '--use_cuda', 'True']
mt1_cmd = ['python', 'languages.py', '--model', 'lstm', '--dataset', 'nc_zhen', '--task', 'mt', '--batch_size', '32' ,'--use_cuda', 'True']
mt2_cmd = ['python', 'languages.py', '--model', 'transformer', '--dataset', 'nc_zhen', '--task', 'mt', '--batch_size', '16', '--use_cuda', 'True']
nvprof_prefix_cmd = ['nvprof', '--profile-from-start', 'off', 
                     '--csv',]
models_train = {
    'googlenet_cmd': googlenet_cmd,
    'mobilenetv2_cmd': mobilenetv2_cmd,
    'vgg19_cmd': vgg19_cmd,
    'pos_cmd': pos_cmd,
    'mt1_cmd': mt1_cmd,
    'mt2_cmd': mt2_cmd,
    # 'mobilenet_v2_035_batch_16': mobile_net_v2_035_b16_cmd,
    # 'mobilenet_v1_025_batch_40': mobile_net_v1_025_cmd,
    # 'mobilenet_v1_025_batch_48': mobile_net_v1_025_b48_cmd,
    # 'mobilenet_v1_025_batch_32': mobile_net_v1_025_b32_cmd,
    # 'ptb_word_lm': ptb_word_lm_cmd,
    # 'nasnet_batch_8': nasnet_b8_cmd,
    # 'resnet_50_batch8_cmd': resnet_50_b8_cmd,
    # 'resnet_v1_50_batch_8': resnet_50_v1_b8_cmd,
    # 'resnet_v1_50_batch_16': resnet_50_v1_b16_cmd,
    # 'vgg19_batch_8': vgg_19_b8_cmd,
    # 'vgg16_batch_8': vgg_16_b8_cmd,
    # 'alexnet_v2_batch_8': alexnet_v2_b8_cmd,
    # 'inceptionv1_batch_8': inception_v1_b8_cmd,
    # 'inceptionv2_batch_8': inception_v2_b8_cmd,
    # 'inceptionv3_batch_8': inception_v3_b8_cmd,
    # 'inceptionv4_batch_8': inception_v4_b8_cmd,
    # 'resnet_101_v1_batch_8': resnet_101_v1_b8_cmd,
    # 'resnet_151_v1_batch_8': resnet_152_v1_b8_cmd,
    # 'debug': debug_cmd,
    'nvprof_prefix': nvprof_prefix_cmd
}

def process(line):
    # assuming always have sec/step
    if 'sec/step' in line:
        return line.split('(', 1)[1].split('sec')[0]
    else:
        return 0.0

def get_average_num_step(file_path):
    num = 0.0
    mean = 0.0
    with open(file_path, 'r') as f:
        for line in f:
            if 'sec/step' in line:
                mean = mean * num
                time_elapsed = process(line)
                num += 1
                mean = (mean + float(time_elapsed)) / num
    return (num, mean)

def create_process(model_name, index, experiment_path, percent=0.0, is_nvprof=False, nvprof_args=None):
    execution_id = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    output_dir_name = execution_id+model_name+str(index)
    if is_nvprof:
        output_dir_name = 'nvprof' + output_dir_name
    output_dir = os.path.join(experiment_path, output_dir_name)
    output_file = os.path.join(output_dir, 'output.log') 
    err_out_file = os.path.join(output_dir, 'err.log') 
    train_dir = os.path.join(output_dir, 'experiment')

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists(train_dir):
        os.makedirs(train_dir)

    err = open(err_out_file, 'w+')
    out = open(output_file, 'w+')
    cmd = None
    cmd = copy.deepcopy(models_train[model_name])
    curr_dir = os.path.abspath(os.path.dirname(__file__))
    cmd = cmd + ['--dataset_dir', curr_dir]
    cmd = cmd + ['--run_name', output_dir_name]
    
    if is_nvprof:
        nvprof_log = os.path.join(train_dir, 'nvprof_log.log')
        nv_prefix = models_train['nvprof_prefix']
        nv_prefix += ['--log-file', nvprof_log]
        if nvprof_args is not None:
            nv_prefix += nvprof_args
        cmd = nv_prefix + cmd
    
    print(cmd)
    p = subprocess.Popen(cmd, stdout=out, stderr=err)
    return (p, out, err, output_file, output_dir)

def kill_process_safe(pid, 
                      err_handle, 
                      out_handle, 
                      path, 
                      ids, 
                      accumulated_models, 
                      mean_num_models,
                      mean_time_p_steps,
                      processes_list,
                      err_logs,
                      out_logs,
                      start_times,
                      err_file_paths,
                      i):
    err_handle.close()
    out_handle.close()
    path_i = path
    num, mean = get_average_num_step(path_i)
    model_index = ids[pid]
    mean_num_models[model_index] = ((accumulated_models[model_index] * mean_num_models[model_index]) + num) / (accumulated_models[model_index] + 1.0)
    mean_time_p_steps[model_index] = ((accumulated_models[model_index] * mean_time_p_steps[model_index]) + mean) / (accumulated_models[model_index] + 1.0)
    accumulated_models[model_index] += 1.0
    processes_list.pop(i)
    err_logs.pop(i)
    out_logs.pop(i)
    start_times.pop(i)
    err_file_paths.pop(i)
    return mean, num
    
_RUNS_PER_SET = 2
_START = 1

def run(
    average_log, experiment_path, 
    experiment_set, total_length, 
    experiment_index):
    
    if not os.path.exists(experiment_path):
        os.makedirs(experiment_path)

    mean_num_models = np.zeros(len(experiment_set), dtype=float)
    mean_time_p_steps = np.zeros(len(experiment_set), dtype=float)
    accumulated_models = np.zeros(len(experiment_set), dtype=float)

    is_single = len(experiment_set) == 1

    nvidia_smi_cmd = ['watch', '-n', '0.2', 'nvidia-smi', 
                              '--query-gpu=memory.used,memory.total,utilization.gpu,utilization.memory,power.draw', 
                              '--format=noheader,csv', '|', 'tee', '-a' , experiment_path+'/smi_watch.csv']

    if is_single:
        # 1. we want to use nvprof once for single model and obtain metrics.
        nvp, out, err, path, out_dir = create_process(experiment_set[0], 1, experiment_path, 0.92, True, 
            ['--timeout', str(60*3),
             '--metrics', 'achieved_occupancy,ipc,sm_efficiency,dram_write_transactions,dram_write_throughput,dram_read_transactions,dram_read_throughput,dram_utilization,flop_count_dp,',])
        while nvp.poll() is None:
            print("nvprof profiling metrics %s" % experiment_set[0])
            time.sleep(2)
        out.close()
        err.close()
        
    for experiment_run in range(_START, _START+_RUNS_PER_SET):
        if os.path.exists(average_log):
            average_file = open(average_log, mode='a+')
        else:
            average_file = open(average_log, mode='w+')
        processes_list = []
        err_logs = []
        out_logs = []
        out_file_paths = []
        start_times = []
        ids = {}
        percent = (1 / len(experiment_set)) - 0.075 # some overhead of cuda stuff i think :/
        for i, m in enumerate(experiment_set):
            start_time = time.time()
            p, out, err, path, out_dir = create_process(m, i, experiment_path, percent)
            processes_list.append(p)
            err_logs.append(err)
            out_logs.append(out)
            start_times.append(start_time)
            out_file_paths.append(path)
            ids[p.pid] = i
        should_stop = False
        sys_tracker = sys_track.SystemInfoTracker(experiment_path)

        # 2. we should do a timeline profile.
        if experiment_run == 1:
            # nvprof timeline here
            timeline_file_path = os.path.join(experiment_path, 'timeline_err.log')
            timeline_file = open(timeline_file_path, 'a+')
            timeline_prof_file = os.path.join(experiment_path, '%p_timeline')
            nvprof_all_cmd = ['nvprof', '--profile-all-processes', '--trace', 'gpu', '--timeout', str(30), '-o', timeline_prof_file ]

            prof_timeline = subprocess.Popen(nvprof_all_cmd, stdout=timeline_file, stderr=timeline_file)
            prof_poll = None

        try:
            smi_file_path = os.path.join(experiment_path, 'smi_out.log') 
            smi_file = open(smi_file_path, 'a+')
            
            smi_p = subprocess.Popen(nvidia_smi_cmd, stdout=smi_file, stderr=smi_file)
            smi_poll = None
            sys_tracker.start()
            while not should_stop:
                time.sleep(5)
                if len(processes_list) <= 0:
                    should_stop = True

                for i,(p, err, out, start_time, path) in enumerate(zip(processes_list, err_logs, out_logs, start_times, out_file_paths)):
                    poll = None
                    pid = p.pid
                    poll = p.poll()
                    current_time = time.time()
                    executed = current_time - start_time
                    if poll is None:
                        print('Process %d still running' % pid)
                    else:
                        mean, num = kill_process_safe(pid, err, out, path, ids, accumulated_models, 
                                                      mean_num_models, mean_time_p_steps, processes_list, err_logs, out_logs, start_times, out_file_paths, i)
                        line = ("experiment set %d, experiment_run %d: %d process average num p step is %.4f and total number of step is: %d \n" % 
                                (experiment_index, experiment_run, pid, mean, num))
                        average_file.write(line)

                smi_poll = smi_p.poll()
                if smi_poll is None:
                    print('NVIDIA_SMI Process %d still running' % smi_p.pid)

            print('total experiments: %d, experiment_run %d , finished %d' % (total_length-1, experiment_run, experiment_index))

        except KeyboardInterrupt:
            smi_p.kill()
            smi_file.close()
            for p, err, out in zip(processes_list, err_logs, out_logs):
                pid = p.pid
                p.kill()
                err.close()
                out.close()
                print('%d killed ! ! !' % pid)
        finally:
             smi_poll = smi_p.poll()
             if smi_poll is None:
                smi_p.kill()
                smi_file.close()
        
        average_file.close()
        sys_tracker.stop()

        prof_poll = prof_timeline.poll()
        while prof_poll is None:
            time.sleep(30)
            print("waiting for nvprof to finish.")
            prof_poll = prof_timeline.poll()
            prof_timeline.kill()
        print("nvprof finished")
        timeline_file.close()

    # Experiment average size.
    average_file = open(average_log, mode='a+')
    for i in range(len(experiment_set)):
        average_file.write("TOTAL: In experiment %d average mean sec/step and average number for model %d are %.4f , %d \n" % 
                        (experiment_index, i, mean_time_p_steps[i], mean_num_models[i]))
    average_file.close()
    
def main():
    # which one we should run in parallel
    sets = [
            ['googlenet_cmd'],
            ['mobilenetv2_cmd'],
            ['vgg19_cmd'],
            ['pos_cmd'],
            ['mt1_cmd'],
            ['mt2_cmd'],
            ['googlenet_cmd','googlenet_cmd'],
            ['mobilenetv2_cmd','mobilenetv2_cmd'],
            ['vgg19_cmd', 'vgg19_cmd'],
            ['pos_cmd', 'pos_cmd'],
            ['mt1_cmd','mt1_cmd'],
            ['googlenet_cmd', 'mobilenetv2_cmd'],
            ['googlenet_cmd', 'vgg19_cmd'],
            ['googlenet_cmd', 'pos_cmd'],
            ['googlenet_cmd', 'mt1_cmd'],
            ['mobilenetv2_cmd', 'vgg19_cmd'],
            ['mobilenetv2_cmd', 'pos_cmd'],
            ['mobilenetv2_cmd', 'mt1_cmd'],
	    ['mobilenetv2_cmd', 'mt2_cmd'] 
           ]
    project_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    experiment_path = os.path.join(project_dir, 'experiment')

    for experiment_index, ex in enumerate(sets):
        current_experiment_path = os.path.join(experiment_path, str(experiment_index))
        experiment_file = os.path.join(experiment_path, 'experiment.log')

        run(experiment_file, current_experiment_path, ex, len(sets), experiment_index)
if __name__ == "__main__":
    main()
        
