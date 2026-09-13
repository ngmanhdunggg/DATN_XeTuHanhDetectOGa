import torch
import torch
from model.TwinLite import TwinLiteNet
import torch.backends.cudnn as cudnn
import DataSet as myDataLoader
from argparse import ArgumentParser
from utils import val, netParams
import torch.optim.lr_scheduler
from const import *

def validation(args):
    # load the model
    model = TwinLiteNet()
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        model = torch.nn.DataParallel(model)
        model = model.cuda()
        cudnn.benchmark = True

    # Dataset với root_dir và valid=True (lấy phần val)
    val_dataset = myDataLoader.MyDataset(root_dir=args.data_root, valid=True, train_ratio=0.8, seed=42)
    valLoader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers, pin_memory=True)

    total_params = netParams(model)
    print('Total network parameters: ' + str(total_params))
    
    model.load_state_dict(torch.load(args.weight))
    model.eval()
    # Không cần jit trace nếu không muốn, nhưng giữ nguyên
    example = torch.rand(1, 3, 360, 640).cuda()
    model = torch.jit.trace(model, example)
    da_segment_results, ll_segment_results = val(valLoader, model)

    msg = ('Driving area Segment: Acc({da_seg_acc:.3f})    IOU ({da_seg_iou:.3f})    mIOU({da_seg_miou:.3f})\n'
           'Lane line Segment: Acc({ll_seg_acc:.3f})    IOU ({ll_seg_iou:.3f})  mIOU({ll_seg_miou:.3f})').format(
               da_seg_acc=da_segment_results[0], da_seg_iou=da_segment_results[1], da_seg_miou=da_segment_results[2],
               ll_seg_acc=ll_segment_results[0], ll_seg_iou=ll_segment_results[1], ll_seg_miou=ll_segment_results[2])
    print(msg)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--data_root', type=str, default='C:/Users/dung2/Desktop/Model/data',
                        help='Path to folder containing images and JSON files')
    parser.add_argument('--weight', default="pretrained/best.pth", help='Path to model weights')
    parser.add_argument('--num_workers', type=int, default=4, help='No. of parallel threads')
    parser.add_argument('--batch_size', type=int, default=8, help='Batch size')
    args = parser.parse_args()
    validation(args)