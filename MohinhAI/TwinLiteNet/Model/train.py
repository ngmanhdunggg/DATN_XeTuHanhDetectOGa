import os
import torch
import matplotlib.pyplot as plt
from model.TwinLite import TwinLiteNet
import torch.backends.cudnn as cudnn
import DataSet as myDataLoader
from argparse import ArgumentParser
from utils import netParams, save_checkpoint, poly_lr_scheduler, SegmentationMetric
from loss import TotalLoss
from tqdm import tqdm

def plot_curves(epoch, train_losses, val_losses, val_da_miou, val_ll_miou, save_dir):
    """Vẽ và lưu 2 đồ thị: Loss (train+val) và mIoU (val DA & LL)"""
    plt.clf()
    epochs = range(1, len(train_losses) + 1)
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Loss
    axes[0].plot(epochs, train_losses, 'b-', label='Train Loss')
    axes[0].plot(epochs, val_losses, 'r-', label='Val Loss')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].set_title('Loss')
    axes[0].legend()
    axes[0].grid(True)
    
    # mIoU
    axes[1].plot(epochs, val_da_miou, 'g-', label='Drivable Area mIoU')
    axes[1].plot(epochs, val_ll_miou, 'm-', label='Lane Line mIoU')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('mIoU')
    axes[1].set_title('Validation mIoU')
    axes[1].legend()
    axes[1].grid(True)
    
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, 'training_curves.png'), dpi=150)
    plt.close()

@torch.no_grad()
def val_with_loss(val_loader, model, criterion, args):
    """Tính loss và metrics (mIoU) trên tập validation"""
    model.eval()
    total_loss = 0.0
    num_batches = 0
    DA = SegmentationMetric(2)
    LL = SegmentationMetric(2)
    
    for _, input, target in val_loader:
        if args.onGPU:
            input = input.cuda().float()
            target = (target[0].cuda(), target[1].cuda())
        output = model(input)
        _, _, loss = criterion(output, target)
        total_loss += loss.item()
        num_batches += 1
        
        out_da, out_ll = output
        target_da, target_ll = target
        _, da_predict = torch.max(out_da, 1)
        _, da_gt = torch.max(target_da, 1)
        _, ll_predict = torch.max(out_ll, 1)
        _, ll_gt = torch.max(target_ll, 1)
        
        DA.addBatch(da_predict.cpu(), da_gt.cpu())
        LL.addBatch(ll_predict.cpu(), ll_gt.cpu())
    
    avg_loss = total_loss / num_batches
    da_miou = DA.meanIntersectionOverUnion()
    ll_miou = LL.meanIntersectionOverUnion()
    return avg_loss, da_miou, ll_miou

def train_net(args):
    cuda_available = torch.cuda.is_available()
    num_gpus = torch.cuda.device_count()
    model = TwinLiteNet()
    if num_gpus > 1:
        model = torch.nn.DataParallel(model)

    args.savedir = args.savedir + '/'
    if not os.path.exists(args.savedir):
        os.makedirs(args.savedir)

    train_dataset = myDataLoader.MyDataset(root_dir=args.data_root, valid=False, train_ratio=0.8, seed=42)
    val_dataset = myDataLoader.MyDataset(root_dir=args.data_root, valid=True, train_ratio=0.8, seed=42)

    trainLoader = torch.utils.data.DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=True)
    valLoader = torch.utils.data.DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=args.num_workers, pin_memory=True)

    if cuda_available:
        args.onGPU = True
        model = model.cuda()
        cudnn.benchmark = True
    else:
        args.onGPU = False

    total_params = netParams(model)
    print('Total network parameters: ' + str(total_params))

    criteria = TotalLoss()
    start_epoch = 0
    optimizer = torch.optim.Adam(model.parameters(), args.lr, (0.9, 0.999), eps=1e-08, weight_decay=5e-4)

    if args.resume:
        if os.path.isfile(args.resume):
            print("=> loading checkpoint '{}'".format(args.resume))
            checkpoint = torch.load(args.resume)
            start_epoch = checkpoint['epoch']
            model.load_state_dict(checkpoint['state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer'])
            print("=> loaded checkpoint '{}' (epoch {})".format(args.resume, checkpoint['epoch']))

    train_losses = []
    val_losses = []
    val_da_mious = []
    val_ll_mious = []

    for epoch in range(start_epoch, args.max_epochs):
        model_file_name = args.savedir + os.sep + 'model_{}.pth'.format(epoch)
        poly_lr_scheduler(args, optimizer, epoch)
        lr = optimizer.param_groups[0]['lr']
        print("Learning rate: " + str(lr))

        # --- Train ---
        model.train()
        total_loss = 0.0
        num_batches = 0
        pbar = tqdm(enumerate(trainLoader), total=len(trainLoader), bar_format='{l_bar}{bar:10}{r_bar}')
        for i, (_, input, target) in pbar:
            if args.onGPU:
                input = input.cuda().float()
                target = (target[0].cuda(), target[1].cuda())
            output = model(input)
            optimizer.zero_grad()
            _, _, loss = criteria(output, target)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            num_batches += 1
            pbar.set_description(f'{epoch}/{args.max_epochs - 1} | Loss: {loss.item():.4f}')
        avg_train_loss = total_loss / num_batches
        train_losses.append(avg_train_loss)

        # --- Validation (có loss và mIoU) ---
        val_loss, da_miou, ll_miou = val_with_loss(valLoader, model, criteria, args)
        val_losses.append(val_loss)
        val_da_mious.append(da_miou)
        val_ll_mious.append(ll_miou)

        print(f"Train Loss: {avg_train_loss:.4f} | Val Loss: {val_loss:.4f}")
        print(f"Drivable Area mIoU: {da_miou:.3f} | Lane Line mIoU: {ll_miou:.3f}")

        torch.save(model.state_dict(), model_file_name)
        save_checkpoint({
            'epoch': epoch + 1,
            'state_dict': model.state_dict(),
            'optimizer': optimizer.state_dict(),
            'lr': lr
        }, args.savedir + 'checkpoint.pth.tar')

        # Vẽ đồ thị sau mỗi epoch
        plot_curves(epoch+1, train_losses, val_losses, val_da_mious, val_ll_mious, args.savedir)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--data_root', type=str, default='C:/Users/dung2/Desktop/Model/data',
                        help='Path to folder containing images and JSON files')
    parser.add_argument('--max_epochs', type=int, default=250)
    parser.add_argument('--num_workers', type=int, default=2)
    parser.add_argument('--batch_size', type=int, default=4)
    parser.add_argument('--lr', type=float, default=5e-4)
    parser.add_argument('--savedir', default='./pretrained3')
    parser.add_argument('--resume', type=str, default='')
    parser.add_argument('--pretrained3', default='')
    args = parser.parse_args()
    train_net(args)

# python train.py --resume ./pretrained3/checkpoint.pth.tar --data_root C:/Users/dung2/Desktop/Model/data --savedir ./pretrained3 --max_epochs 300 --batch_size 8 --lr 5e-4