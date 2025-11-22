import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { TacacsNgSettingPublic } from "@/client"
import EditTacacsNgSetting from "../TacacsNgSettings/EditTacacsNgSetting"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface TacacsNgSettingActionsMenuProps {
  tacacs_ng_setting: TacacsNgSettingPublic
}

export const TacacsNgSettingActionsMenu = ({ tacacs_ng_setting }: TacacsNgSettingActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditTacacsNgSetting tacacs_ng_setting={tacacs_ng_setting} />
      </MenuContent>
    </MenuRoot>
  )
}
