import os
import time
import numpy as np
import pandas as pd
import requests

import tensorflow as tf
from tensorflow import keras
from tensorflow.python.saved_model import tag_constants


from tensorflow.keras.applications import ( 
    vgg16,
    resnet50,
    inception_v3,
    mobilenet_v2,
    xception,
)
models = {
    'xception':xception,
    'vgg16':vgg16,
    'resnet50':resnet50,
    'inception_v3':inception_v3,
    'mobilenet_v2':mobilenet_v2
}

def deserialize_image_record(record):
    feature_map = {'image/encoded': tf.io.FixedLenFeature([], tf.string, ''),
                  'image/class/label': tf.io.FixedLenFeature([1], tf.int64, -1),
                  'image/class/text': tf.io.FixedLenFeature([], tf.string, '')}
    obj = tf.io.parse_single_example(serialized=record, features=feature_map)
    imgdata = obj['image/encoded']
    label = tf.cast(obj['image/class/label'], tf.int32)   
    label_text = tf.cast(obj['image/class/text'], tf.string)   
    return imgdata, label, label_text

def val_preprocessing(record):
    imgdata, label, label_text = deserialize_image_record(record)
    label -= 1
    image = tf.io.decode_jpeg(imgdata, channels=3, 
                              fancy_upscaling=False, 
                              dct_method='INTEGER_FAST')

    shape = tf.shape(image)
    height = tf.cast(shape[0], tf.float32)
    width = tf.cast(shape[1], tf.float32)
    side = tf.cast(tf.convert_to_tensor(256, dtype=tf.int32), tf.float32)

    scale = tf.cond(tf.greater(height, width),
                  lambda: side / width,
                  lambda: side / height)
    
    new_height = tf.cast(tf.math.rint(height * scale), tf.int32)
    new_width = tf.cast(tf.math.rint(width * scale), tf.int32)
    
    image = tf.image.resize(image, [new_height, new_width], method='bicubic')
    image = tf.image.resize_with_crop_or_pad(image, 224, 224)
    
    image = models[model].preprocess_input(image)
    
    return image, label, label_text

def get_dataset(batchsize):
    data_dir = '/workspace/datasets/*'
    files = tf.io.gfile.glob(os.path.join(data_dir))
    dataset = tf.data.TFRecordDataset(files)
    
    dataset = dataset.map(map_func=val_preprocessing, num_parallel_calls=tf.data.experimental.AUTOTUNE)
    dataset = dataset.batch(batch_size=batchsize)
    dataset = dataset.prefetch(buffer_size=tf.data.experimental.AUTOTUNE)
    dataset = dataset.repeat(count=1)
    
    return dataset


def trt_predict_benchmark(trt_compiled_model_dir,precision, batchsize, display_every=5000, warm_up=50):

    print('\n============================================================')
    print(f'{trt_compiled_model_dir} - inference batch size: {batchsize}')
    print('=============================================================\n')
    
    dataset = get_dataset(batchsize)
    
    #compile한 model engine load 
    saved_model_trt = tf.saved_model.load(trt_compiled_model_dir, tags=[tag_constants.SERVING])
    model_trt = saved_model_trt.signatures['serving_default']

    pred_labels = []
    actual_labels = []
    iter_times = []
    
    display_threshold = display_every

    walltime_start = time.time()
    N=0
    for i, (validation_ds, batch_labels, _) in enumerate(dataset):
        N+=1
        if i==0:
            for w in range(warm_up):
                _ = model_trt(validation_ds);
                
        start_time = time.time()
        trt_results = model_trt(validation_ds);
        iter_times.append(time.time() - start_time)
        
        actual_labels.extend(label for label_list in batch_labels.numpy() for label in label_list)
        pred_labels.extend(list(tf.argmax(trt_results['predictions'], axis=1).numpy()))
        if (i)*batchsize >= display_threshold:
            print(f'Images {(i)*batchsize}/50000. Average i/s {np.mean(batchsize/np.array(iter_times[-display_every:]))}')
            display_threshold+=display_every
    
    print('Throughput: {:.0f} images/s'.format(N * batchsize / sum(iter_times)))

    acc_trt = np.sum(np.array(actual_labels) == np.array(pred_labels))/len(actual_labels)
    iter_times = np.array(iter_times)
   
    results = pd.DataFrame(columns = [f'trt_{precision}_{batchsize}'])
    results.loc['instance_type']           = [requests.get('http://169.254.169.254/latest/meta-data/instance-type').text]
    results.loc['batchsize']               = [batchsize]
    results.loc['accuracy']                = [acc_trt]
    results.loc['prediction_time']         = [np.sum(iter_times)]
    results.loc['wall_time']               = [time.time() - walltime_start]   
    results.loc['images_per_sec_mean']     = [np.mean(batchsize / iter_times)]
    results.loc['images_per_sec_std']      = [np.std(batchsize / iter_times, ddof=1)]
    results.loc['latency_mean']            = [np.mean(iter_times) * 1000]
    results.loc['latency_99th_percentile'] = [np.percentile(iter_times, q=99, interpolation="lower") * 1000]
    results.loc['latency_median']          = [np.median(iter_times) * 1000]
    results.loc['latency_min']             = [np.min(iter_times) * 1000]
    results.loc['first_batch']             = [iter_times[0]*1000]
    results.loc['next_batches_mean']       = [np.mean(iter_times[1:])*1000]
    print(results)
   
    return results, iter_times


if __name__ == "__main__":
    import argparse

    results = None
    parser = argparse.ArgumentParser()
    parser.add_argument('--model',default='resnet50' , type=str)
    parser.add_argument('--batchsize',default=1,type=int)
    parser.add_argument('--engine_batch',default=8,type=int)
    parser.add_argument('--precision',default='FP32',type=str)
    args = parser.parse_args()
    model = args.model
    batchsize = args.batchsize
    engine_batch = args.engine_batch
    precision = args.precision

    trt_compiled_model_dir = f'{model}_{precision}_{engine_batch}'

    print("------TENSORRT_INFERENCE-------")
    trt_predict_benchmark(trt_compiled_model_dir,precision, batchsize)
