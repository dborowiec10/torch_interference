import os
import multiprocessing
import time 
import numpy as np
import csv
import models_to_run
import copy

def get_app_finish_time(output_log):
  sets = copy.deepcopy(models_to_run.sets)

  models = [
    'pos_cmd', 
    'mt1', 
    'mt2', 
    'lm_cmd', 
    'resnet', 
    'googlenet', 
    'mobilenetv2', 
    'vgg19',
    'lm_large',]

  set_num = int(os.path.basename(os.path.dirname(os.path.dirname(output_log))))
  run_name = sets[set_num]
  with open(output_log, 'r', encoding='utf8') as outlog_f:
    for line in outlog_f:
      if "Finished" in line and "training" not in line:
        temp = line.split("ran for")[1].split("secs")[0].strip()

        model = None
        for m in models:
          if m in os.path.dirname(output_log):
            model = m
        return run_name, temp, model

def main():
  app_output_logs = []
  for dir_path, subdirs, filenames in os.walk(os.getcwd()):
    for fn in filenames:
      if "nvprof" in dir_path: continue
      if "err.log" in fn and "-timeline" not in fn:
        app_output_log = os.path.join(dir_path, fn)
        app_output_logs.append(app_output_log)
  start_time = time.time()
  with multiprocessing.Pool(processes=6) as pools:
    res = pools.map(get_app_finish_time, app_output_logs)
  finished_time = time.time() - start_time
  print(finished_time)
  results = {}
  apptime_f = os.path.join(os.getcwd(), "application_time.csv")
  with open(apptime_f, 'w+') as app_time_handle:
    field_names = ['model_runs', 'model', 'application_runtime(s)']
    csv_writer = csv.DictWriter(app_time_handle, field_names, delimiter=',', lineterminator='\n')
    csv_writer.writeheader()
    for obj in res:
      try:
        if obj is None: continue
        k, v, m = obj
        csv_writer.writerow({'model_runs':k, 'model': m,'application_runtime(s)': v})
      except:
        print("%s failed to write" % k)
if __name__ == "__main__":
  main()