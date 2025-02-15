import torch
from torch import nn
import torch.nn.functional as F
import torchsummary
import torch
import pytorch_lightning as pl
import random
import common as com
from dlcliche.utils import *


def load_weights(model, weight_file):
    model.load_state_dict(torch.load(weight_file))


def summary(device, model, input_size=(1, 640)):
    torchsummary.summary(model.to(device), input_size=input_size)


def summarize_weights(model):
    summary = pd.DataFrame()
    for k, p in model.state_dict().items():
        p = p.cpu().numpy()
        df = pd.Series(p.ravel()).describe()
        summary.loc[k, 'mean'] = df['mean']
        summary.loc[k, 'std'] = df['std']
        summary.loc[k, 'min'] = df['min']
        summary.loc[k, 'max'] = df['max']
    return summary


def show_some_predictions(dl, model, start_index, n_samples, image=False):
    shape = (-1, 64, 64) if image else (-1, 640)
    x, y = next(iter(dl))
    x, y = x.to(device), y.to(device)
    with torch.no_grad():
        yhat = model(x)
    x = x.cpu().numpy().reshape(shape)
    yhat = yhat.cpu().numpy().reshape(shape)
    print(x.shape, yhat.shape)
    for sample_idx in range(start_index, start_index + n_samples):
        fig, axs = plt.subplots(1, 2, figsize=(10, 5))
        if image:
            axs[0].imshow(x[sample_idx])
            axs[1].imshow(yhat[sample_idx])
        else:
            axs[0].plot(x[sample_idx])
            axs[1].plot(yhat[sample_idx])


def normalize_0to1(X):
    # Normalize to range from [-90, 24] to [0, 1] based on dataset quick stat check.
    X = (X + 90.) / (24. + 90.)
    X = np.clip(X, 0., 1.)
    return X


class ToTensor1ch(object):
    """PyTorch basic transform to convert np array to torch.Tensor.
    Args:
        array: (dim,) or (batch, dims) feature array.
    """
    def __init__(self, device=None, image=False):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.non_batch_shape_len = 2 if image else 1

    def __call__(self, array):
        # (dims)
        if len(array.shape) == self.non_batch_shape_len:
            return torch.Tensor(array).unsqueeze(0).to(self.device)
        # (batch, dims)
        return torch.Tensor(array).unsqueeze(1).to(self.device)

    def __repr__(self):
        return 'to_tensor_1d'


########################################################################
# PyTorch utilities
########################################################################

# class Task2Dataset(torch.utils.data.Dataset):
#     """PyTorch dataset class for task2. Caching to a file supported.

#     Args:
#         n_mels, frames, n_fft, hop_length, power, transform: Audio conversion settings.
#         normalize: Normalize data value range from [-90, 24] to [0, 1] for VAE, False by default.
#         cache_to: Cache filename or None by default, use this for your iterative development.
#     """

#     def __init__(self, files, n_mels, frames, n_fft, hop_length, power, transform,
#                  normalize=False, cache_to=None):
#         self.transform = transform
#         self.files = files
#         self.n_mels, self.frames, self.n_fft = n_mels, frames, n_fft
#         self.hop_length, self.power = hop_length, power
#         # load cache or convert all the data for the first time
#         if cache_to is not None and Path(cache_to).exists():
#             com.logger.info(f'Loading cached {Path(cache_to).name}')
#             self.X = np.load(cache_to)
#         else:
#             self.X = com.list_to_vector_array(self.files,
#                              n_mels=self.n_mels,
#                              frames=self.frames,
#                              n_fft=self.n_fft,
#                              hop_length=self.hop_length,
#                              power=self.power)
#             if cache_to is not None:
#                 np.save(cache_to, self.X)

#         if normalize:
#             self.X = normalize_0to1(self.X)

#     def __len__(self):
#         return len(self.X)

#     def __getitem__(self, index):
#         x = self.X[index]
#         x = self.transform(x)
#         return x, x


class Task2Dataset(torch.utils.data.Dataset):
    """PyTorch dataset class for task2. Caching to a file supported.

    Args:
        n_mels, frames, n_fft, hop_length, power, transform: Audio conversion settings.
        normalize: Normalize data value range from [-90, 24] to [0, 1] for VAE, False by default.
        cache_to: Cache filename or None by default, use this for your iterative development.
    """

    def __init__(self, files, n_mels, frames, n_fft, hop_length, power, transform,
                 normalize=False, cache_to=None):
        self.transform = transform
        self.files = files
        self.n_mels, self.frames, self.n_fft = n_mels, frames, n_fft
        self.hop_length, self.power = hop_length, power
        # load cache or convert all the data for the first time
        if cache_to is not None and Path(cache_to).exists():
            com.logger.info(f'Loading cached {Path(cache_to).name}')
            self.X = np.load(cache_to)
        else:
            self.X = com.list_to_vector_array(self.files,
                             n_mels=self.n_mels,
                             frames=self.frames,
                             n_fft=self.n_fft,
                             hop_length=self.hop_length,
                             power=self.power)
            if cache_to is not None:
                np.save(cache_to, self.X)

        if normalize:
            self.X = normalize_0to1(self.X)

        self.X = torch.stack([self.transform(x) for x in self.X])

        # Transfer the entire dataset to GPU
        self.X = self.X.to('cuda')

    def __len__(self):
        return len(self.X)

    def __getitem__(self, index):
        x = self.X[index]
        return x, x


# class Task2Lightning(pl.LightningModule):
#     """Task2 PyTorch Lightning class, for training only."""

#     def __init__(self, device, model, params, files, normalize=False):
#         super().__init__()
#         self.device = device
#         self.params = params
#         self.normalize = normalize
#         self.model = model
#         self.mseloss = torch.nn.MSELoss()
#         # split data files
#         if files is not None:
#             n_val = int(params.fit.validation_split * len(files))
#             self.val_files = random.sample(files, n_val)
#             self.train_files = [f for f in files if f not in self.val_files]

#     def forward(self, x):
#         return self.model(x)

#     def training_step(self, batch, batch_nb):
#         x, y = batch
#         y_hat = self.forward(x)
#         loss = self.mseloss(y_hat, y)
#         tensorboard_logs = {'train_loss': loss}
#         return {'loss': loss, 'log': tensorboard_logs}

#     def validation_step(self, batch, batch_nb):
#         x, y = batch
#         y_hat = self.forward(x)
#         return {'val_loss': self.mseloss(y_hat, y)}

#     def validation_epoch_end(self, outputs):
#         avg_loss = torch.stack([x['val_loss'] for x in outputs]).mean()
#         tensorboard_logs = {'val_loss': avg_loss}
#         return {'avg_val_loss': avg_loss, 'log': tensorboard_logs}

#     def configure_optimizers(self):
#         return torch.optim.Adam(self.parameters(), lr=self.params.fit.lr,
#                                 betas=(self.params.fit.b1, self.params.fit.b2),
#                                 weight_decay=self.params.fit.weight_decay)

#     def _get_dl(self, for_what):
#         files = self.train_files if for_what == 'train' else self.val_files
#         cache_file = f'{self.params.model_directory}/__cache_{str(files[0]).split("/")[-3]}_{for_what}.npy'
#         ds = Task2Dataset(files,
#                           n_mels=self.params.feature.n_mels,
#                           frames=self.params.feature.frames,
#                           n_fft=self.params.feature.n_fft,
#                           hop_length=self.params.feature.hop_length,
#                           power=self.params.feature.power,
#                           transform=com.ToTensor1ch(device=self.device),
#                           normalize=self.normalize,
#                           cache_to=cache_file)
#         return torch.utils.data.DataLoader(ds, batch_size=self.params.fit.batch_size,
#                           shuffle=(self.params.fit.shuffle if for_what == 'train' else False))

#     def train_dataloader(self):
#         return self._get_dl('train')

#     def val_dataloader(self):
#         return self._get_dl('val')


##My corrected version:
#@title Task2Lightning
class Task2Lightning(pl.LightningModule):
    """Task2 PyTorch Lightning class, for training only."""

    def __init__(self, device, model, params, files, normalize=False):
        super().__init__()
        self.params = params
        self.normalize = normalize
        self.model = model
        self.mseloss = torch.nn.MSELoss()
        self.device_Mine = device
        # split data files
        if files is not None:
            n_val = int(params.fit.validation_split * len(files))
            self.val_files = random.sample(files, n_val)
            self.train_files = [f for f in files if f not in self.val_files]
        # self.val_output_list = []  # Store validation outputs here

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_nb):
        x, y = batch
        y_hat = self.forward(x)
        loss = self.mseloss(y_hat, y)
        self.log("train_loss", loss, on_step=True, on_epoch=True, prog_bar=True, logger=True)
        return loss

    # def on_validation_epoch_start(self) -> None:
    #     super().on_validation_epoch_start()
    #     # self.val_output_list = []
    #     return

    def validation_step(self, batch, batch_nb):
        x, y = batch
        y_hat = self.forward(x)
        mseloss=self.mseloss(y_hat, y)
        # self.val_output_list.append(results)
        # self.log('val_loss', results,step=True, on_epoch=True)## added by me
        self.log("val_loss", mseloss, on_step=True, on_epoch=True, prog_bar=True, logger=True)

    # def  on_validation_epoch_end(self):
    #     # aggregated_result = sum(self.val_output_list) / len(self.val_output_list)
    #     # self.log('val_loss_epoch', aggregated_result)
    #     self.validation_outputs = []

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.params.fit.lr,
                                betas=(self.params.fit.b1, self.params.fit.b2),
                                weight_decay=self.params.fit.weight_decay)

    def _get_dl(self, for_what):
        files = self.train_files if for_what == 'train' else self.val_files
        # cache_file = f'{self.params.model_directory}/__cache_{str(files[0]).split("/")[-3]}_{for_what}.npy'
        cache_file=None
        ds = Task2Dataset(files,
                          n_mels=self.params.feature.n_mels,
                          frames=self.params.feature.frames,
                          n_fft=self.params.feature.n_fft,
                          hop_length=self.params.feature.hop_length,
                          power=self.params.feature.power,
                          transform= ToTensor1ch(device=self.device_Mine),## change this specifically not com by pytorch com
                          normalize=self.normalize,
                          cache_to=cache_file)
        return torch.utils.data.DataLoader(ds, batch_size=self.params.fit.batch_size,
                          shuffle=(self.params.fit.shuffle if for_what == 'train' else False))

    def train_dataloader(self):
        return self._get_dl('train')

    def val_dataloader(self):
        return self._get_dl('val')