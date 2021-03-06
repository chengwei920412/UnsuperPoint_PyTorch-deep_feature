import os
import torch
import cv2
import numpy as np
import math
import argparse
from Unsuper.utils import common_utils
from Unsuper.configs.config import cfg, cfg_from_list, cfg_from_yaml_file
from symbols.get_model import get_sym

# 增加可读性
import matplotlib.pyplot as plt

# 提取不同层输出的 主要代码
class LayerActivations:
    features = None

    def __init__(self, model, layer_num):
        self.hook = model[layer_num].register_forward_hook(self.hook_fn)

    def hook_fn(self, module, input, output):
        self.features = output.cpu()

    def remove(self):
        self.hook.remove()

def parse_config():
    parser = argparse.ArgumentParser(description='arg parser')
    parser.add_argument('--cfg_file', type=str, default='../Unsuper/configs/UnsuperPoint_coco.yaml',
                        help='specify the config for training')

    parser.add_argument('--batch_size', type=int, default=1, required=False, help='batch size for training')
    parser.add_argument('--workers', type=int, default=4, help='number of workers for dataloader')
    # parser.add_argument('--extra_tag', type=str, default='no_score', help='extra tag for this experiment')
    parser.add_argument('--ckpt', type=str, default=None, help='checkpoint to start from')
    parser.add_argument('--set', dest='set_cfgs', default=None, nargs=argparse.REMAINDER,
                        help='set extra config keys if needed')
    parser.add_argument('--start_epoch', type=int, default=0, help='')
    # parser.add_argument('--eval_tag', type=str, default='default', help='eval tag for this experiment')
    parser.add_argument('--eval_all', action='store_true', default=True, help='whether to evaluate all checkpoints')
    parser.add_argument('--ckpt_dir', type=str, default=None, help='specify a ckpt directory to be evaluated if needed')
    parser.add_argument('--save_to_file', action='store_true', default=False, help='')

    args = parser.parse_args()

    cfg_from_yaml_file(args.cfg_file, cfg)
    # cfg.TAG = Path(args.cfg_file).stem
    cfg.EXP_GROUP_PATH = '/'.join(args.cfg_file.split('/')[1:-1])  # remove 'cfgs' and 'xxxx.yaml'
    if args.set_cfgs is not None:
        cfg_from_list(args.set_cfgs, cfg)

    return args, cfg

def main():
    dist_test = False
    args, cfg = parse_config()

    ckpt_dir = '../output/ckpt/checkpoint_epoch_10.pth'

    model = get_sym(model_config=cfg['MODEL'], image_shape=cfg['data']['IMAGE_SHAPE'], is_training=False)

    eval_out_dir = './test_image_log/'
    if os.path.exists(eval_out_dir):
        print('dir exists')
    else:
        os.mkdir(eval_out_dir, 777)

    logger = common_utils.create_logger(eval_out_dir + 'eval_image.txt')

    with torch.no_grad():
        model.load_params_from_file(filename=ckpt_dir, logger=logger, to_cpu=dist_test)
        model.cuda()
        model.eval()

        img = cv2.imread('../img/grid1.jpg')

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        new_h, new_w = cfg['data']['IMAGE_SHAPE']

        resize_img = cv2.resize(img, (new_w, new_h))
        src_img = torch.tensor(resize_img, dtype=torch.float32)
        src_img = torch.unsqueeze(src_img, 0)
        src_img = src_img.permute(0, 3, 1, 2)
        img0_tensor = src_img.cuda()
        # pred_dict = model.predict(img0_tensor)

        # # to onnx
        # input_names = ['input']
        # output_names = ['score', 'position', 'descriptor']
        # torch.onnx.export(model, img0_tensor, '../output/usp.onnx', input_names=input_names, output_names=output_names,
        #                   verbose=True)#, keep_initializers_as_inputs=True, opset_version=11
        # # flops
        # flops, params = profile(model, inputs=(img0_tensor,))
        # flops, params = clever_format([flops, params], "%.3f")
        # print('flops:', flops, 'params:', params)
        # exit(0)

        print(model)

        # conv_out = LayerActivations(model.base_model.cnn, 17)  # 提出第 一个卷积层的输出
        conv_out = LayerActivations(model.score, 4)  # 提出第 一个卷积层的输出
        # conv_out = LayerActivations(model.position, 0)  # 提出第 一个卷积层的输出
        # conv_out = LayerActivations(model.descriptor, 0)  # 提出第 一个卷积层的输出

        # imshow(img)
        pred_dict = model.predict(img0_tensor)
        conv_out.remove()  #
        act = conv_out.features  # act 即 第0层输出的特征
        print(act.shape)
        # 可视化 输出
        fig = plt.figure(figsize=(32, 24))
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1, hspace=0.5, wspace=0.5)
        cols = act.shape[1] if act.shape[1] < 12 else 12

        for i in range(act.shape[1]):
            ax = fig.add_subplot(math.ceil(act.shape[1] / cols + 0.5), cols, i + 1, xticks=[], yticks=[])  # 总行数，总列数，图的位置
            # print(act[0][i].detach().numpy())
            ax.imshow(act[0][i].detach().numpy(), cmap="gray")

        plt.show()
        exit(0)
        for j in pred_dict.keys():
            # cv2.imwrite(os.path.join(str(data_dir), img_name+suffix), img0[j])
            s1 = pred_dict[j]['s1']
            loc = np.where(s1 > 0.7)
            p1 = pred_dict[j]['p1'][loc]
            d1 = pred_dict[j]['d1'][loc]
            s1 = s1[loc]
            # print(p1)
            img = cv2.cvtColor(resize_img, cv2.COLOR_RGB2BGR)
            for i in range(p1.shape[0]):
                pos = p1[i]
                cv2.circle(img, (int(pos[0]), int(pos[1])), 1, (0, 0, 255), 1)

            cv2.imshow('key point', img)
            cv2.waitKey(0)
            # cv2.imwrite(eval_out_dir + 'eval' + '.jpg', img)

if __name__ == '__main__':
    main()
