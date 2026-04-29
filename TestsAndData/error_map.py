import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

a = pd.read_csv(
    "TestsAndData/FLIR0050_temperatures.csv",
    skiprows=5,
    header=None
    ).to_numpy()

b = pd.read_csv(
    "TestsAndData/FLIR0051_temperatures.csv",
    skiprows=5,
    header=None
    ).to_numpy()

print("shape of a is", a.shape)
print("shape of b is", b.shape)

plt.subplot(2,1,1)
plt.imshow(a)

plt.subplot(2,1,2)
plt.imshow(b)


plt.show()
