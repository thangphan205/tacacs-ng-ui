import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import { type TacacsConfigPublic } from "@/client"
import DeleteTacacsConfig from "../TacacsConfigs/DeleteTacacsConfig"
import EditTacacsConfig from "../TacacsConfigs/EditTacacsConfig"
import ShowTacacsConfig from "../TacacsConfigs/ShowTacacsConfig"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface TacacsConfigActionsMenuProps {
  tacacs_config: TacacsConfigPublic
}

export const TacacsConfigActionsMenu = ({ tacacs_config }: TacacsConfigActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <ShowTacacsConfig tacacs_config={tacacs_config} />
        <EditTacacsConfig tacacs_config={tacacs_config} />
        <DeleteTacacsConfig tacacs_config={tacacs_config} />
      </MenuContent>
    </MenuRoot>
  )
}
