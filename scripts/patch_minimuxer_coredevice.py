#!/usr/bin/env python3

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit(
        "usage: patch_minimuxer_coredevice.py <minimuxer-directory>"
    )

root = Path(sys.argv[1]).resolve()
cargo = root / "Cargo.toml"
install = root / "src/install.rs"

if not cargo.is_file() or not install.is_file():
    raise SystemExit(f"Not a minimuxer source tree: {root}")

cargo_text = cargo.read_text(encoding="utf-8")
src = install.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# Cargo
#
# Keep upstream idevice 0.1.29 for the existing JIT implementation.
# Add the B1a-patched idevice tree under a second crate name.
# ---------------------------------------------------------------------

old_dep = 'idevice = { version = "0.1.29", features = ["full"] }'
core_dep = (
    'idevice_core = { package = "idevice", '
    'path = "../../../idevice/idevice", features = ["full"] }'
)

if core_dep not in cargo_text:
    if old_dep not in cargo_text:
        raise SystemExit("Expected idevice 0.1.29 dependency not found")
    cargo_text = cargo_text.replace(
        old_dep,
        old_dep
        + "\n\n"
        + "# SideStore AutoRefresh B1b CoreDevice/RSD backend.\n"
        + core_dep,
        1,
    )

cargo.write_text(cargo_text, encoding="utf-8")

# ---------------------------------------------------------------------
# install.rs
# ---------------------------------------------------------------------

marker = "// SIDESTORE_AUTOREFRESH_COREDEVICE_B1B"

if marker in src:
    print("B1b minimuxer patch already applied")
    raise SystemExit(0)

# Imports used only by the new transport.
imports = '''// SIDESTORE_AUTOREFRESH_COREDEVICE_B1B
use std::{
    net::{Ipv4Addr, SocketAddrV4},
    str::FromStr,
};

use idevice_core::{
    afc::{AfcClient as CoreAfcClient, opcode::AfcFopenMode},
    core_device_proxy::CoreDeviceProxy,
    installation_proxy::InstallationProxyClient as CoreInstallationProxyClient,
    provider::{IdeviceProvider, RsdProvider, TcpProvider},
    rsd::RsdHandshake,
    usbmuxd::{UsbmuxdAddr, UsbmuxdConnection},
    IdeviceService, RsdService,
};

'''

needle = "use log::{error, info};"
if needle not in src:
    raise SystemExit("Expected install.rs import anchor not found")

src = src.replace(needle, imports + needle, 1)

# Remove imports that belonged only to the legacy AFC/InstallationProxy path.
for obsolete in (
    "use plist::{Dictionary, Value};\n",
    "use plist_plus::Plist;\n",
    "use rusty_libimobiledevice::services::afc::AfcFileMode;\n",
):
    src = src.replace(obsolete, "", 1)

src = src.replace(
    "    Errors, PlistPlusConversion, Res, RUNTIME,\n",
    "    Errors, Res, RUNTIME,\n",
    1,
)

# Runtime is needed for the async CoreDevice implementation.
old_crate = '''    device::{fetch_first_device, test_device_connection},
    Errors, PlistPlusConversion, Res,
};'''

new_crate = '''    device::{fetch_first_device, test_device_connection},
    Errors, PlistPlusConversion, Res, RUNTIME,
};'''

if old_crate not in src:
    raise SystemExit("Expected crate import block not found")

src = src.replace(old_crate, new_crate, 1)

# PlistPlusConversion belonged only to the legacy InstallationProxy path.
src = src.replace(
    "    Errors, PlistPlusConversion, Res, RUNTIME,\n",
    "    Errors, Res, RUNTIME,\n",
    1,
)

# ---------------------------------------------------------------------
# Shared CoreDevice/RSD context.
#
# Pairing is intentionally obtained from the existing local usbmuxd
# endpoint, exactly like minimuxer's existing iOS 17+ JIT path.
# Device transport itself then uses LocalDevVPN 10.7.0.1.
# ---------------------------------------------------------------------

anchor = 'const PKG_PATH: &str = "PublicStaging";'

helper = r'''
const COREDEVICE_ADDR: &str = "10.7.0.1";
const USBMUXD_ADDR: &str = "127.0.0.1:27015";

async fn coredevice_rsd_context(
) -> Result<(idevice_core::tcp::handle::AdapterHandle, RsdHandshake), Errors> {
    let usbmux_socket = SocketAddrV4::from_str(USBMUXD_ADDR)
        .map_err(|_| Errors::NoConnection)?;

    let stream = tokio::net::TcpStream::connect(usbmux_socket)
        .await
        .map_err(|e| {
            error!("CoreDevice: unable to connect to local usbmuxd: {e:?}");
            Errors::NoConnection
        })?;

    let mut uc = UsbmuxdConnection::new(Box::new(stream), 0);

    let device = uc
        .get_devices()
        .await
        .map_err(|e| {
            error!("CoreDevice: unable to enumerate usbmuxd devices: {e:?}");
            Errors::NoConnection
        })?
        .into_iter()
        .next()
        .ok_or(Errors::NoConnection)?;

    let usbmux_provider = device.to_provider(
        UsbmuxdAddr::TcpSocket(std::net::SocketAddr::V4(usbmux_socket)),
        "minimuxer-coredevice",
    );

    let pairing_file = usbmux_provider
        .get_pairing_file()
        .await
        .map_err(|e| {
            error!("CoreDevice: unable to obtain pairing file: {e:?}");
            Errors::NoConnection
        })?;

    let provider = TcpProvider {
        addr: std::net::IpAddr::V4(
            Ipv4Addr::from_str(COREDEVICE_ADDR)
                .map_err(|_| Errors::NoConnection)?,
        ),
        scope_id: None,
        pairing_file,
        label: "minimuxer-coredevice".to_string(),
    };

    let proxy = CoreDeviceProxy::connect(&provider)
        .await
        .map_err(|e| {
            error!("CoreDeviceProxy connection failed: {e:?}");
            Errors::CreateCoreDevice
        })?;

    let rsd_port = proxy.tunnel_info().server_rsd_port;

    let adapter = proxy.create_software_tunnel().map_err(|e| {
        error!("CoreDevice software tunnel failed: {e:?}");
        Errors::CreateSoftwareTunnel
    })?;

    let mut handle = adapter.to_async_handle();

    let rsd_stream = handle
        .connect_to_service_port(rsd_port)
        .await
        .map_err(|e| {
            error!("CoreDevice RSD connection failed: {e:?}");
            Errors::Connect
        })?;

    let handshake = RsdHandshake::new(rsd_stream)
        .await
        .map_err(|e| {
            error!("CoreDevice RSD handshake failed: {e:?}");
            Errors::XpcHandshake
        })?;

    info!(
        "CoreDevice/RSD ready with {} advertised services",
        handshake.services.len()
    );

    Ok((handle, handshake))
}
'''

if anchor not in src:
    raise SystemExit("PKG_PATH anchor not found")

src = src.replace(anchor, anchor + "\n" + helper, 1)

# ---------------------------------------------------------------------
# Replace only the two refresh transport functions.
# remove_app() deliberately remains on the upstream implementation.
# ---------------------------------------------------------------------

start = src.find("pub fn yeet_app_afc(")
end = src.find("/// Removes an app from the device")

if start < 0 or end < 0 or end <= start:
    raise SystemExit("Could not locate refresh function block")

replacement = r'''pub fn yeet_app_afc(bundle_id: String, ipa_bytes: &[u8]) -> Res<()> {
    info!(
        "CoreDevice/RSD: staging IPA for bundle ID: {}",
        bundle_id
    );

    RUNTIME.block_on(async {
        let (mut handle, mut handshake) = coredevice_rsd_context().await?;

        let mut afc = CoreAfcClient::connect_rsd(&mut handle, &mut handshake)
            .await
            .map_err(|e| {
                error!("CoreDevice/RSD: unable to connect AFC: {e:?}");
                Errors::CreateAfc
            })?;

        // Preserve SideStore's existing two-stage remote path exactly.
        afc.mk_dir(PKG_PATH).await.ok();

        let bundle_dir = format!("{PKG_PATH}/{bundle_id}");
        afc.mk_dir(&bundle_dir).await.ok();

        let remote_path = format!("{bundle_dir}/app.ipa");

        let mut fd = afc
            .open(&remote_path, AfcFopenMode::WrOnly)
            .await
            .map_err(|e| {
                error!(
                    "CoreDevice/RSD: unable to open {remote_path}: {e:?}"
                );
                Errors::RwAfc
            })?;

        fd.write_entire(ipa_bytes).await.map_err(|e| {
            error!("CoreDevice/RSD: unable to write IPA: {e:?}");
            Errors::RwAfc
        })?;

        fd.close().await.map_err(|e| {
            error!("CoreDevice/RSD: unable to close IPA: {e:?}");
            Errors::RwAfc
        })?;

        info!("CoreDevice/RSD: IPA staging complete");
        Ok(())
    })
}

/// Installs an ipa with a bundle ID.
/// Expects the IPA to have been staged by yeet_app_afc().
pub fn install_ipa(bundle_id: String) -> Res<()> {
    info!(
        "CoreDevice/RSD: installing app for bundle ID: {}",
        bundle_id
    );

    RUNTIME.block_on(async {
        // A new context is intentional: SendAppOperation and
        // InstallAppOperation are separate SideStore operations.
        let (mut handle, mut handshake) = coredevice_rsd_context().await?;

        let mut inst =
            CoreInstallationProxyClient::connect_rsd(
                &mut handle,
                &mut handshake,
            )
            .await
            .map_err(|e| {
                error!(
                    "CoreDevice/RSD: unable to connect InstallationProxy: {e:?}"
                );
                Errors::CreateInstproxy
            })?;

        let remote_path =
            format!("{PKG_PATH}/{bundle_id}/app.ipa");

        let options = plist::Value::Dictionary(
            [(
                "CFBundleIdentifier".to_string(),
                plist::Value::String(bundle_id.clone()),
            )]
            .into_iter()
            .collect(),
        );

        inst.install(remote_path, Some(options))
            .await
            .map_err(|e| {
                error!("CoreDevice/RSD installation failed: {e:?}");
                Errors::InstallApp(format!("{e:?}"))
            })?;

        info!("CoreDevice/RSD: installation complete");
        Ok(())
    })
}

'''

src = src[:start] + replacement + src[end:]

install.write_text(src, encoding="utf-8")

print(f"Applied native Rust CoreDevice/RSD refresh patch to {root}")
